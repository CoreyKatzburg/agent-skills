from fastapi import Request

from app.config import PUBLIC_BASE_URL


def public_base_url(request: Request) -> str:
    """The address agents should use to reach this server, without a trailing slash."""
    return PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
