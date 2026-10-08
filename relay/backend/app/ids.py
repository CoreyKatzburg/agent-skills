"""Id and secret generation."""

import re
import secrets
import string

LOWERCASE_ALPHANUMERIC = string.ascii_lowercase + string.digits

# Batch ids are short words so they are easy for an agent to read back and echo.
BATCH_WORDS = (
    "amber", "anchor", "apple", "arrow", "aspen", "basil", "beacon", "birch", "bloom", "breeze",
    "brook", "cedar", "cinder", "clover", "comet", "coral", "crane", "delta", "ember", "falcon",
    "fern", "flint", "frost", "garnet", "glade", "harbor", "hazel", "heron", "indigo", "iris",
    "jade", "juniper", "kestrel", "lagoon", "lantern", "lark", "lotus", "maple", "meadow", "mesa",
    "nectar", "nova", "oak", "onyx", "orchid", "pebble", "pine", "plume", "quartz", "raven",
    "reef", "river", "sage", "slate", "sparrow", "spruce", "summit", "thistle", "tide", "willow",
)  # fmt: skip


def random_lowercase(length: int) -> str:
    return "".join(secrets.choice(LOWERCASE_ALPHANUMERIC) for _ in range(length))


def slugify(text: str, max_length: int = 24) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].strip("-")


def new_channel_id() -> str:
    return random_lowercase(12)


def new_message_id() -> str:
    return f"thread_{random_lowercase(16)}"


def new_participant_id(display_name: str) -> str:
    """A readable id like "release-bot-k3j9x0a1b2c3" that stays the same after renames."""
    return f"{slugify(display_name) or 'participant'}-{random_lowercase(12)}"


def new_secret() -> str:
    """For user ids and agent tokens: long enough that nobody can guess one."""
    return secrets.token_urlsafe(24)


def new_batch_id() -> str:
    return f"{secrets.choice(BATCH_WORDS)}-{secrets.choice(BATCH_WORDS)}-{secrets.randbelow(1000):03d}"
