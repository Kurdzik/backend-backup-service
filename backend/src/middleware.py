import logging
import os
import time

from fastapi import FastAPI, HTTPException, status, Security
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.security.api_key import APIKeyHeader
from src.models import Session as UserSession
from src.models import User

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
session = Session(engine)
logger = logging.getLogger(__name__)
session_token_header = APIKeyHeader(name="X-Session-Token", auto_error=False)


class SQLAlchemySessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, db_session_factory: Session):
        super().__init__(app)
        self.db_session_factory: Session = db_session_factory

    async def dispatch(self, request: Request, call_next):
        request.state.db = self.db_session_factory
        try:
            response = await call_next(request)
            request.state.db.commit()
        except SQLAlchemyError:
            request.state.db.rollback()
            raise
        finally:
            request.state.db.close()
        return response


def check_token(request: Request, token: str = Security(session_token_header)):

    request.state.user_id = None
    request.state.tenant_id = None

    excluded_paths = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/users/register",
        "/api/v1/users/login",
        "/api/v1/users/change-password",
    ]

    if request.url.path in excluded_paths or request.method == "OPTIONS":
        return

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token required",
        )

    try:
        statement = select(UserSession).where(UserSession.token == token)
        user_session = request.state.db.exec(statement).one()

        statement = select(User).where(User.id == user_session.user_id)
        user = request.state.db.exec(statement).one()

        request.state.user_id = user_session.user_id
        request.state.tenant_id = user.tenant_id

    except Exception as e:
        logger.error(f"Auth failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Session token"
        )