from fastapi import Request
from sqlmodel import Session
from pydantic import BaseModel

class UserInfo(BaseModel):
    user_id: int
    tenant_id: str

def get_db_session(request: Request) -> Session:
    return request.state.db

def get_user_info(request: Request) -> UserInfo:
    return UserInfo(
        user_id=request.state.user_id,
        tenant_id=request.state.tenant_id
    )
