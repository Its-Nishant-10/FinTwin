"""FastAPI entrypoint.

Run locally:  make backend      (or: uvicorn app.main:app --reload)
Docs:         http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import agent, documents, health, portfolio, profile, scenario
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("FinTwin backend starting (env=%s)", settings.app_env)
    # Member 2: open the DB pool / warm the market-data cache here.
    yield
    log.info("FinTwin backend shutting down")


app = FastAPI(
    title="FinTwin API",
    description=(
        "Explainable AI personal finance intelligence & simulation. "
        "Research prototype — not regulated investment advice."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(profile.router)
app.include_router(portfolio.router)
app.include_router(scenario.router)
app.include_router(agent.router)
app.include_router(documents.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "FinTwin", "version": __version__, "docs": "/docs"}
