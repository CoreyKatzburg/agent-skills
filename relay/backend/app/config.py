"""Settings and limits. Every setting can be overridden with an environment variable."""

import os
from pathlib import Path

APP_NAME = "Relay"

# SQLite keeps everything in one local file, so no data leaves the machine.
DATABASE_URL = os.environ.get("RELAY_DATABASE_URL", "sqlite:///./relay.db")

# The address agents should use to reach this server, e.g. "https://relay.mycompany.com".
# When unset, the address of the incoming request is used.
PUBLIC_BASE_URL = os.environ.get("RELAY_PUBLIC_BASE_URL", "").rstrip("/")

# The built React app. When this folder exists, the backend serves the frontend too.
FRONTEND_DIST_DIR = Path(
    os.environ.get(
        "RELAY_FRONTEND_DIST_DIR",
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    )
)

MAX_DISPLAY_NAME_LENGTH = 40
MAX_CHANNEL_NAME_LENGTH = 80
MAX_MESSAGE_LENGTH = 12_288
MAX_MENTIONED_PARTICIPANTS = 20
MAX_PARTICIPANTS_PER_CHANNEL = 100
MAX_CHANNELS_PER_USER = 50

ACTIVITY_BATCH_SIZE = 10
MAX_ACTIVITY_WAIT_SECONDS = 50
# An agent counts as online when it has polled for activity within this window.
AGENT_ONLINE_WINDOW_SECONDS = 120

MESSAGE_PAGE_SIZE = 50
PERSON_ACTIVITY_FEED_SIZE = 50
