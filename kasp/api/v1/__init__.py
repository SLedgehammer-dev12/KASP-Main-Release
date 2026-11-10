"""KASP Web API v1 Package.

Aggregates all modular v1 subrouters into a unified api_v1 APIRouter.
"""

from fastapi import APIRouter

from kasp.api.v1.auth import router as auth_router
from kasp.api.v1.users import router as users_router
from kasp.api.v1.metadata import router as metadata_router
from kasp.api.v1.calculations import router as calculations_router
from kasp.api.v1.equipment import router as equipment_router
from kasp.api.v1.projects import router as projects_router
from kasp.api.v1.reports import router as reports_router
from kasp.api.v1.jobs import router as jobs_router
from kasp.api.v1.logs import router as logs_router
from kasp.api.v1.modules import router as modules_router

api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(metadata_router)
api_v1.include_router(calculations_router)
api_v1.include_router(equipment_router)
api_v1.include_router(projects_router)
api_v1.include_router(reports_router)
api_v1.include_router(jobs_router)
api_v1.include_router(logs_router)
api_v1.include_router(modules_router)
