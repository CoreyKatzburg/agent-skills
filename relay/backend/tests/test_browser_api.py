from fastapi.testclient import TestClient

from app.mentions import MentionCandidate, resolve_mentions
from tests.conftest import new_request_id, register_agent


def make_user(client: TestClient, name: str) -> dict:
    user = client.post("/v1/users", json={"displayName": name}).json()
    return {"user": user, "headers": {"X-User-Id": user["id"]}}


def test_creating_a_channel_joins_the_owner(client, owner):
    channel_id = owner["channel"]["id"]
    assert owner["channel"]["isOwner"] is True
    assert owner["channel"]["me"]["displayName"] == "Corey"

    feed = client.get(f"/v1/channels/{channel_id}/messages").json()
    assert [(m["senderDisplay"], m["body"]) for m in feed["messages"]] == [("Corey", "joined the channel")]
    my_channels = client.get("/v1/users/me/channels", headers=owner["headers"]).json()
    assert my_channels["owned"] == [{"id": channel_id, "name": "Design review"}]


def test_guests_can_read_but_must_join_to_post(client, owner):
    channel_id = owner["channel"]["id"]
    guest = make_user(client, "Sam")
    assert client.get(f"/v1/channels/{channel_id}", headers=guest["headers"]).json()["me"] is None

    payload = {"body": "hi", "requestId": new_request_id(), "threadId": "general"}
    assert client.post(f"/v1/channels/{channel_id}/messages", json=payload, headers=guest["headers"]).status_code == 403

    client.post(f"/v1/channels/{channel_id}/join", headers=guest["headers"])
    assert client.post(f"/v1/channels/{channel_id}/messages", json=payload, headers=guest["headers"]).status_code == 200
    shared = client.get("/v1/users/me/channels", headers=guest["headers"]).json()["shared"]
    assert [c["id"] for c in shared] == [channel_id]


def test_only_the_owner_can_rename_or_delete(client, owner):
    channel_id = owner["channel"]["id"]
    guest = make_user(client, "Sam")
    client.post(f"/v1/channels/{channel_id}/join", headers=guest["headers"])

    assert client.patch(f"/v1/channels/{channel_id}", json={"name": "x"}, headers=guest["headers"]).status_code == 403
    renamed = client.patch(f"/v1/channels/{channel_id}", json={"name": "#launch"}, headers=owner["headers"])
    assert renamed.json()["name"] == "launch"

    assert client.delete(f"/v1/channels/{channel_id}", headers=guest["headers"]).status_code == 403
    assert client.delete(f"/v1/channels/{channel_id}", headers=owner["headers"]).status_code == 204
    assert client.get(f"/v1/channels/{channel_id}").status_code == 404


def test_deleting_a_message_leaves_a_tombstone(client, owner):
    channel_id = owner["channel"]["id"]
    payload = {"body": "oops", "requestId": new_request_id(), "threadId": "general"}
    message = client.post(f"/v1/channels/{channel_id}/messages", json=payload, headers=owner["headers"]).json()

    deleted = client.delete(f"/v1/channels/{channel_id}/messages/{message['threadId']}", headers=owner["headers"])
    assert deleted.status_code == 204
    last = client.get(f"/v1/channels/{channel_id}/messages").json()["messages"][-1]
    assert last["deleted"] is True
    assert last["body"] == ""


def test_renaming_a_user_renames_them_everywhere(client, owner):
    client.patch("/v1/users/me", json={"displayName": "Corey K"}, headers=owner["headers"])
    participants = client.get(f"/v1/channels/{owner['channel']['id']}/participants").json()["participants"]
    assert [p["displayName"] for p in participants] == ["Corey K"]


def test_person_activity_shows_mentions_and_followed_replies(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    root = client.post(
        f"/v1/channels/{channel_id}/messages",
        json={"body": "Topic", "requestId": new_request_id(), "threadId": "general"},
        headers=owner["headers"],
    ).json()
    client.get(
        f"/v1/channels/{channel_id}/agent/send",
        params={"token": agent["token"], "message": "Reply", "requestId": new_request_id(), "replyToMessageId": root["threadId"]},
    )

    feed = client.get("/v1/users/me/activity", headers=owner["headers"]).json()
    assert [(item["message"]["body"], item["reasons"]) for item in feed["items"]] == [("Reply", ["following"])]
    assert feed["unreadCount"] == 1

    client.post("/v1/users/me/activity/read", headers=owner["headers"])
    assert client.get("/v1/users/me/activity", headers=owner["headers"]).json()["unreadCount"] == 0


def test_live_updates_push_new_messages(client, owner):
    channel_id = owner["channel"]["id"]
    with client.websocket_connect(f"/v1/channels/{channel_id}/live") as socket:
        socket.send_json({"userId": owner["user"]["id"]})
        assert socket.receive_json() == {"type": "participants"}  # we came online
        client.post(
            f"/v1/channels/{channel_id}/messages",
            json={"body": "live!", "requestId": new_request_id(), "threadId": "general"},
            headers=owner["headers"],
        )
        event = socket.receive_json()
        assert event["type"] == "message"
        assert event["message"]["body"] == "live!"


def test_mentions_skip_code_links_emails_and_ambiguous_names():
    candidates = [
        MentionCandidate("ann-1", "Ann"),
        MentionCandidate("ann-lee-2", "Ann Lee"),
        MentionCandidate("bo-3", "Bo"),
        MentionCandidate("bo-4", "Bo"),
    ]
    body, ids = resolve_mentions(
        "@ann lee and @Ann, not `@ann` or a@ann.com or \\@ann or @bo or @Anna, but @bo-4",
        candidates,
    )
    assert body == "@ann-lee-2 and @ann-1, not `@ann` or a@ann.com or \\@ann or @bo or @Anna, but @bo-4"
    assert ids == ["ann-lee-2", "ann-1", "bo-4"]
