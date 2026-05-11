import json
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from sqlalchemy import create_engine
from sqlmodel import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from src import configure_logger, get_logger, log_context, tenant_context

from src.middleware import (
    RequestContextMiddleware,
    SQLAlchemySessionMiddleware,
    session,
)
from src.utils import get_db_session, get_user_info
from fastapi.middleware.cors import CORSMiddleware
from src.models import *
import sqlmodel
from src.api import api_router

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api.system")
logger = get_logger("api.system")

app = FastAPI(
    title="Backend",
    redoc_url="/docs",
    docs_url=None,
    default_response_class=ORJSONResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(SQLAlchemySessionMiddleware, db_session_factory=session)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, detail: str, request: Request) -> ORJSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = {"detail": detail}
    if request_id:
        payload["request_id"] = request_id
    return ORJSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"

    if status_code >= 500:
        with log_context(request_id=request_id, service_name="api.error"):
            logger.error(
                "http_exception",
                status_code=status_code,
                detail=detail,
                method=request.method,
                path=request.url.path,
                exc_info=True,
            )
    else:
        with log_context(request_id=request_id, service_name="api.error"):
            logger.warning(
                "request_rejected",
                status_code=status_code,
                detail=detail,
                method=request.method,
                path=request.url.path,
            )

    return _error_response(status_code, detail, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    with log_context(request_id=request_id, service_name="api.error"):
        logger.warning(
            "request_validation_failed",
            method=request.method,
            path=request.url.path,
            errors=exc.errors(),
        )
    return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid request payload", request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    with log_context(
        request_id=request_id,
        tenant_id=getattr(request.state, "tenant_id", None),
        service_name="api.error",
    ):
        logger.error(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )

    detail = "Internal server error"
    if request_id:
        detail = f"{detail}. Reference: {request_id}"
    return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, detail, request)

@api_router.get("/system/logs", response_model=ApiResponse)
def get_system_logs(
    limit: int = Query(default=100, ge=1, le=500),
    min_level: str = Query(default="warning", pattern="^(debug|info|warning|error|critical)$"),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    try:
        statement = (
            select(Logs)
            .where(Logs.tenant_id == user_info.tenant_id)
            .order_by(Logs.timestamp.desc())
            .limit(limit * 5)
        )

        level_rank = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}
        min_rank = level_rank[min_level]
        logs = []

        for log_entry in db_session.exec(statement).all():
            try:
                log_level = json.loads(log_entry.log).get("level", "info")
            except json.JSONDecodeError:
                log_level = "info"

            if level_rank.get(log_level, 20) >= min_rank:
                logs.append(log_entry)

            if len(logs) >= limit:
                break

        return ApiResponse(message="Logs retrieved successfully", data={"logs": logs})

    except Exception as e:
        with tenant_context(tenant_id=user_info.tenant_id, service_name="api.system"):
            logger.error("failed_to_retrieve_docker_logs", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system logs",
        )


app.include_router(api_router)
