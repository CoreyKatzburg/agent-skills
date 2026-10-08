"""Browser user accounts. The browser stores the user id and sends it in the X-User-Id header."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import User
from app.schemas import (
    PersonActivityResponse,
    UserChannelsResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import activity, channels, participants

router = APIRouter(prefix="/v1/users", tags=["browser"])

DatabaseSession = Annotated[Session, Depends(get_session)]


def current_user(
    session: DatabaseSession, user_id: Annotated[str | None, Header(alias="X-User-Id")] = None
) -> User:
    return channels.find_user(session, user_id)


CurrentUser = Annotated[User, Depends(current_user)]


def present_user(user: User) -> UserOut:
    return UserOut(id=user.id, display_name=user.display_name)


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, session: DatabaseSession) -> UserOut:
    return present_user(channels.create_user(session, body.display_name))


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser) -> UserOut:
    return present_user(user)


@router.patch("/me", response_model=UserOut)
def rename_me(body: UserUpdate, user: CurrentUser, session: DatabaseSession) -> UserOut:
    return present_user(participants.rename_user(session, user, body.display_name))


@router.get("/me/channels", response_model=UserChannelsResponse)
def my_channels(user: CurrentUser, session: DatabaseSession) -> UserChannelsResponse:
    return channels.list_user_channels(session, user)


@router.get("/me/activity", response_model=PersonActivityResponse)
def my_activity(user: CurrentUser, session: DatabaseSession) -> PersonActivityResponse:
    return activity.person_activity_feed(session, user)


@router.post("/me/activity/read", status_code=204)
def mark_my_activity_read(user: CurrentUser, session: DatabaseSession) -> Response:
    activity.mark_person_activity_read(session, user)
    return Response(status_code=204)
