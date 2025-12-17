import logging
import os
import time

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.models.db import Session as UserSession
from src.models.db import User

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
session = Session(engine)
logger = logging.getLogger(__name__)


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


class ResponseTimeLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time

        logger.info(
            f"Endpoint: {request.method} {request.url.path} | "
            f"Response Time: {process_time:.4f}s | "
            f"Status Code: {response.status_code}"
        )

        response.headers["X-Process-Time"] = str(process_time)

        return response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        excluded_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/users/register",
            "/api/v1/users/login",
            "/api/v1/users/change-password",
        ]

        if request.url.path in excluded_paths:
            response = await call_next(request)
            return response

        # Allow preflight cors check before actual request
        if request.method == "OPTIONS":
            response = await call_next(request)
            return response

        token = request.headers.get("X-Session-Token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token required",
            )

        try:
            statement = select(UserSession).where(UserSession.token == token)
            user_session = session.exec(statement).one()

            statement = select(User).where(User.id == user_session.user_id)
            user = session.exec(statement).one()

            request.state.user_id = user_session.user_id
            request.state.tenant_id = user.tenant_id

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Session token"
            )

        response = await call_next(request)
        return response
