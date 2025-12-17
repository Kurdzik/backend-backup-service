from fastapi import Request
from sqlmodel import Session

from src.models.structs import UserInfo


def get_db_session(request: Request) -> Session:
    return request.state.db


def get_user_info(request: Request) -> UserInfo:
    return UserInfo(user_id=request.state.user_id, tenant_id=request.state.tenant_id)
