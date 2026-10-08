import yaml
from fastapi.testclient import TestClient

from tests.conftest import new_request_id, register_agent


def poll(client: TestClient, channel_id: str, token: str, ack_batch: str | None = None) -> dict:
    params = {"token": token, "wait": 0}
    if ack_batch:
        params["ackBatch"] = ack_batch
    response = client.get(f"/v1/channels/{channel_id}/agent/activity", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def person_posts(client: TestClient, owner: dict, body: str, **target) -> dict:
    payload = {"body": body, "requestId": new_request_id(), **(target or {"threadId": "general"})}
    response = client.post(
        f"/v1/channels/{owner['channel']['id']}/messages", json=payload, headers=owner["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_register_returns_working_urls_and_replay_returns_same_identity(client, owner):
    channel_id = owner["channel"]["id"]
    params = {"name": "Release Bot", "requestId": new_request_id(), "icon": "anthropic"}
    first = client.get(f"/v1/channels/{channel_id}/agent/register", params=params).json()
    replay = client.get(f"/v1/channels/{channel_id}/agent/register", params=params).json()

    assert first["participant"]["id"].startswith("release-bot-")
    assert first["participant"]["icon"] == "anthropic"
    assert replay["token"] == first["token"]
    assert first["activityUrl"].endswith(f"/v1/channels/{channel_id}/agent/activity?token={first['token']}")


def test_activity_batches_replay_until_acknowledged(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    person_posts(client, owner, "Can someone review PR 412?")

    batch = poll(client, channel_id, agent["token"])
    assert batch["batchId"]
    assert [a["message"]["body"] for a in batch["activities"]] == ["Can someone review PR 412?"]
    assert batch["activities"][0]["reasons"] == ["general"]

    # Not acknowledged yet, so the same batch comes back.
    assert poll(client, channel_id, agent["token"])["batchId"] == batch["batchId"]

    # Acknowledged: nothing new is waiting, so the poll times out empty.
    empty = poll(client, channel_id, agent["token"], ack_batch=batch["batchId"])
    assert empty == {"batchId": None, "activities": [], "remainingUnread": 0}

    # Repeating the last acknowledgment is harmless; an unknown one is rejected.
    assert poll(client, channel_id, agent["token"], ack_batch=batch["batchId"])["batchId"] is None
    bad = client.get(
        f"/v1/channels/{channel_id}/agent/activity",
        params={"token": agent["token"], "wait": 0, "ackBatch": "not-a-batch"},
    )
    assert bad.status_code == 409
    assert bad.json()["code"] == "INVALID_ARGUMENT"


def test_batches_hold_at_most_ten_messages(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    for number in range(12):
        person_posts(client, owner, f"message {number}")

    first = poll(client, channel_id, agent["token"])
    assert len(first["activities"]) == 10
    assert first["remainingUnread"] == 2
    second = poll(client, channel_id, agent["token"], ack_batch=first["batchId"])
    assert [a["message"]["body"] for a in second["activities"]] == ["message 10", "message 11"]


def test_agents_only_get_replies_in_threads_they_follow_or_are_mentioned_in(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    root = person_posts(client, owner, "Topic")
    batch = poll(client, channel_id, agent["token"])

    person_posts(client, owner, "A reply the agent does not follow", replyToMessageId=root["threadId"])
    assert poll(client, channel_id, agent["token"], ack_batch=batch["batchId"])["batchId"] is None

    mention = person_posts(client, owner, "@helper what do you think?", replyToMessageId=root["threadId"])
    assert mention["body"] == f"@{agent['participant']['id']} what do you think?"
    batch = poll(client, channel_id, agent["token"], ack_batch=batch["batchId"])
    # Being mentioned also followed the thread, so both reasons apply.
    assert batch["activities"][0]["reasons"] == ["following", "mention"]
    assert batch["activities"][0]["followingThread"] is True

    # Following the thread means later replies arrive too, even without a mention.
    person_posts(client, owner, "Another reply", replyToMessageId=root["threadId"])
    batch = poll(client, channel_id, agent["token"], ack_batch=batch["batchId"])
    assert batch["activities"][0]["reasons"] == ["following"]


def test_send_is_idempotent_and_replies_stay_under_the_root(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    root = person_posts(client, owner, "Topic")
    reply = person_posts(client, owner, "Reply", replyToMessageId=root["threadId"])

    params = {
        "token": agent["token"],
        "message": "Answering the reply",
        "requestId": new_request_id(),
        "replyToMessageId": reply["threadId"],
    }
    sent = client.get(f"/v1/channels/{channel_id}/agent/send", params=params).json()
    retried = client.get(f"/v1/channels/{channel_id}/agent/send", params=params).json()

    assert sent["threadId"] == retried["threadId"]
    assert sent["parentThreadId"] == root["threadId"]
    thread = client.get(f"/v1/channels/{channel_id}/threads/{root['threadId']}").json()
    assert [r["body"] for r in thread["replies"]] == ["Reply", "Answering the reply"]
    assert thread["root"]["replyCount"] == 2


def test_send_needs_exactly_one_target(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    response = client.get(
        f"/v1/channels/{channel_id}/agent/send",
        params={"token": agent["token"], "message": "hi", "requestId": new_request_id()},
    )
    assert response.status_code == 400


def test_leaving_invalidates_the_token_and_replaying_registration_rejoins(client, owner):
    channel_id = owner["channel"]["id"]
    params = {"name": "Helper", "requestId": new_request_id()}
    agent = client.get(f"/v1/channels/{channel_id}/agent/register", params=params).json()

    left = client.get(
        f"/v1/channels/{channel_id}/agent/leave",
        params={"token": agent["token"], "requestId": new_request_id()},
    )
    assert left.status_code == 204
    assert client.get(
        f"/v1/channels/{channel_id}/agent/activity", params={"token": agent["token"], "wait": 0}
    ).status_code == 401

    rejoined = client.get(f"/v1/channels/{channel_id}/agent/register", params=params).json()
    assert rejoined["participant"]["id"] == agent["participant"]["id"]
    assert rejoined["token"] != agent["token"]


def test_removed_agents_cannot_rejoin_with_the_same_registration(client, owner):
    channel_id = owner["channel"]["id"]
    params = {"name": "Helper", "requestId": new_request_id()}
    agent = client.get(f"/v1/channels/{channel_id}/agent/register", params=params).json()

    removed = client.delete(
        f"/v1/channels/{channel_id}/participants/{agent['participant']['id']}",
        headers=owner["headers"],
    )
    assert removed.status_code == 204
    again = client.get(f"/v1/channels/{channel_id}/agent/register", params=params)
    assert again.status_code == 403


def test_rename_keeps_the_id_and_posts_an_event(client, owner):
    channel_id = owner["channel"]["id"]
    agent = register_agent(client, channel_id, "Helper")
    renamed = client.get(
        f"/v1/channels/{channel_id}/agent/rename",
        params={"token": agent["token"], "name": "Reviewer", "icon": "openai", "requestId": new_request_id()},
    ).json()

    assert renamed["id"] == agent["participant"]["id"]
    assert renamed["displayName"] == "Reviewer"
    feed = client.get(f"/v1/channels/{channel_id}/messages").json()["messages"]
    assert feed[-1]["kind"] == "event"
    assert feed[-1]["body"] == "changed their name to Reviewer and changed their icon"


def test_names_with_at_signs_are_rejected(client, owner):
    response = client.get(
        f"/v1/channels/{owner['channel']['id']}/agent/register",
        params={"name": "@everyone", "requestId": new_request_id()},
    )
    assert response.status_code == 400


def test_instructions_document_lists_only_agent_endpoints(client, owner):
    channel_id = owner["channel"]["id"]
    response = client.get(f"/v1/channels/{channel_id}/openapi.yaml")
    document = yaml.safe_load(response.text)

    assert document["servers"][0]["url"].endswith(f"/v1/channels/{channel_id}")
    assert set(document["paths"]) == {
        "/agent/register",
        "/agent/activity",
        "/agent/send",
        "/agent/follow",
        "/agent/rename",
        "/agent/leave",
        "/participants",
    }
    register_parameters = [p["name"] for p in document["paths"]["/agent/register"]["get"]["parameters"]]
    assert "channel_id" not in register_parameters
    assert "AgentIcon" in document["components"]["schemas"]
