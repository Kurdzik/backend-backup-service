import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import ORJSONResponse
from sqlalchemy import create_engine
from sqlmodel import select

from src import configure_logger, get_logger, tenant_context
from src.middleware import (
    AuthMiddleware,
    ResponseTimeLoggingMiddleware,
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
configure_logger(engine, service_name="api")
logger = get_logger("api")

app = FastAPI(
    title="Backend", 
    redoc_url="/docs", 
    docs_url=None,
    default_response_class=ORJSONResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Bad request"
        },
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized"
        },
        403: {
            "model": ErrorResponse,
            "description": "Forbidden"
        },
        404: {
            "model": ErrorResponse,
            "description": "Not found"
        },
        409: {
            "model": ErrorResponse,
            "description": "Conflict"
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error"
        }
    }
)

app.add_middleware(AuthMiddleware)  # type:ignore[arg-type]
app.add_middleware(ResponseTimeLoggingMiddleware)  # type:ignore[arg-type]
app.add_middleware(SQLAlchemySessionMiddleware, db_session_factory=session)  # type:ignore[arg-type]
app.add_middleware(
    CORSMiddleware,  # type:ignore[arg-type]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

@app.get("/api/v1/system/logs", response_model=ApiResponse)
def get_system_logs(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):

    try:
        statement = select(Logs).where(Logs.tenant_id == user_info.tenant_id)

        logs = db_session.exec(statement).all()

        return ApiResponse(message="Logs retrieved successfully", data={"logs": logs})

    except Exception as e:
        with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
            logger.error("failed_to_retrieve_docker_logs", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system logs",
        )

401, 500, 400, 409, 403, 404