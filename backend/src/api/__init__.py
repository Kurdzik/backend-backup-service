from fastapi import APIRouter
from src.api.user_management import router as user_management_router
from src.api.backup_creation import router as backup_creation_router
from src.api.backup_destinations import router as backup_destination_router
from src.api.backup_schedules import router as backup_schedule_router
from src.api.backup_sources import router as backup_sources_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(user_management_router)
api_router.include_router(backup_creation_router)
api_router.include_router(backup_destination_router)
api_router.include_router(backup_schedule_router)
api_router.include_router(backup_sources_router)


__all__ = ["api_router"]
