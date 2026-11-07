from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    dashboard,
    graph,
    investigations,
    reports,
    repositories,
    risk,
    system,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(repositories.router)
api_router.include_router(graph.router)
api_router.include_router(risk.router)
api_router.include_router(investigations.router)
api_router.include_router(agents.router)
api_router.include_router(reports.router)
