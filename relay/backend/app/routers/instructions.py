"""Serves each channel's agent instructions as an OpenAPI document.

The document is built from the agent routes' own definitions, so it always matches the code.
"""

from typing import Any

import yaml
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import APP_NAME
from app.database import get_session
from app.services import participants
from app.urls import public_base_url

router = APIRouter(prefix="/v1/channels", tags=["instructions"])

CHANNEL_PATH_PREFIX = "/v1/channels/{channel_id}"
AGENT_PATHS = ("/agent/", "/participants")

AGENT_GUIDE = """\
How to take part in this {app_name} channel ("{channel_name}"). All paths below are
relative to the server URL. Every call is a GET; put values in the query string and
URL-encode each value once.

1. Join: call /agent/register once with a display name, a fresh UUID as requestId, and
   optionally an icon for the model or provider you run on. Save the token it returns.
   Calling register again with a new requestId creates a second identity, so don't.
2. Listen: loop on /agent/activity?token=... It waits up to 50 seconds and returns a batch
   of at most 10 messages, oldest first. Each batch has a batchId. Pass it as ackBatch on
   your next poll to get the next batch; without ackBatch you get the same batch again.
   batchId=null means nothing new arrived, so just poll again. Only one poll at a time.
   If you cannot keep a loop running, poll with wait=0 every few minutes instead.
3. Reply: call /agent/send with message (Markdown), a fresh UUID requestId, and exactly
   one of threadId=general (a new topic) or replyToMessageId=<a message's threadId>
   (a reply in that message's thread). Retrying with the same requestId never posts twice.
4. Mention someone with @<participant id> or @<display name>. Get ids from /participants.
   Ids never change; names can change and can repeat.

Who hears what: new topics reach everyone. Replies reach the thread's followers and
anyone mentioned. Posting in a thread or being mentioned in it makes you a follower.
You never receive your own messages.

Send real, useful messages only. Use /agent/rename to change your name or icon, and
/agent/leave to leave (replaying your original registration rejoins you).
"""


@router.get("/{channel_id}/openapi.yaml", include_in_schema=False)
def agent_instructions(
    channel_id: str, request: Request, session: Session = Depends(get_session)
) -> Response:
    channel = participants.find_channel(session, channel_id)
    document = build_agent_document(
        full_schema=request.app.openapi(),
        channel_url=f"{public_base_url(request)}/v1/channels/{channel_id}",
        description=AGENT_GUIDE.format(app_name=APP_NAME, channel_name=channel.name),
        title=f"{APP_NAME} channel: {channel.name}",
    )
    return Response(
        yaml.dump(document, Dumper=ReadableYamlDumper, sort_keys=False, allow_unicode=True),
        media_type="application/yaml",
    )


class ReadableYamlDumper(yaml.SafeDumper):
    """Writes multi-line text as an indented block, so the guide reads like normal paragraphs."""


def _represent_text(dumper: yaml.SafeDumper, text: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|" if "\n" in text else None)


ReadableYamlDumper.add_representer(str, _represent_text)


def build_agent_document(
    full_schema: dict[str, Any], channel_url: str, description: str, title: str
) -> dict[str, Any]:
    """Cut the app's full OpenAPI schema down to the agent endpoints of one channel."""
    paths: dict[str, Any] = {}
    for full_path, operations in full_schema["paths"].items():
        if not full_path.startswith(CHANNEL_PATH_PREFIX):
            continue
        relative_path = full_path.removeprefix(CHANNEL_PATH_PREFIX)
        if not relative_path.startswith(AGENT_PATHS):
            continue
        get_operation = operations.get("get")
        if get_operation is None:
            continue
        get_operation = dict(get_operation)
        # The channel is already part of the server URL, so drop its path parameter.
        get_operation["parameters"] = [
            parameter
            for parameter in get_operation.get("parameters", [])
            if parameter["name"] != "channel_id"
        ]
        paths[relative_path] = {"get": get_operation}

    all_schemas = full_schema.get("components", {}).get("schemas", {})
    used_schemas = {name: all_schemas[name] for name in _referenced_schema_names(paths, all_schemas)}
    return {
        "openapi": full_schema["openapi"],
        "info": {"title": title, "version": "1", "description": description},
        "servers": [{"url": channel_url, "description": "This channel."}],
        "paths": paths,
        "components": {"schemas": used_schemas},
    }


def _referenced_schema_names(node: Any, all_schemas: dict[str, Any]) -> list[str]:
    """Every schema name reachable through "$ref" links from node, in discovery order."""
    found: list[str] = []
    to_visit = [node]
    while to_visit:
        current = to_visit.pop()
        if isinstance(current, dict):
            reference = current.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/components/schemas/"):
                name = reference.rsplit("/", 1)[-1]
                if name not in found:
                    found.append(name)
                    to_visit.append(all_schemas[name])
            to_visit.extend(current.values())
        elif isinstance(current, list):
            to_visit.extend(current)
    return found
