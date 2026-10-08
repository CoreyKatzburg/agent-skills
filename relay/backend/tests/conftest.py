import os
import tempfile
import uuid
from collections.abc import Iterator

import pytest

# Point the app at a throwaway database before any app module is imported.
os.environ["RELAY_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["RELAY_FRONTEND_DIST_DIR"] = "/nonexistent"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def new_request_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def owner(client: TestClient) -> dict:
    """A browser user who owns a fresh channel."""
    user = client.post("/v1/users", json={"displayName": "Corey"}).json()
    headers = {"X-User-Id": user["id"]}
    channel = client.post("/v1/channels", json={"name": "Design review"}, headers=headers).json()
    return {"user": user, "headers": headers, "channel": channel}


def register_agent(client: TestClient, channel_id: str, name: str, icon: str | None = None) -> dict:
    params = {"name": name, "requestId": new_request_id()}
    if icon:
        params["icon"] = icon
    response = client.get(f"/v1/channels/{channel_id}/agent/register", params=params)
    assert response.status_code == 200, response.text
    return response.json()
