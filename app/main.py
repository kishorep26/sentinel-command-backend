import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.logging_setup import setup_logging
from app.core.middleware import RequestTracingMiddleware
from app.core.runtime import IS_SERVERLESS
from app.core.security import limiter
from app.models.models import create_tables
from app.routers import admin, agents, analytics, geocoding, incidents
from app.services import dispatch as dispatch_service
from app.services import simulation as simulation_service
from app.websocket.manager import ws_manager

def _bootstrap_db() -> None:
    try:
        create_tables(engine)
        db = SessionLocal()
        try:
            dispatch_service.seed_agents(db)
            dispatch_service.seed_stats(db)
        finally:
            db.close()
        logger.info("Database bootstrap complete")
    except Exception:
        logger.exception("Database bootstrap failed — will retry on first request")


async def _simulation_loop() -> None:
    logger.info("Simulation loop started (interval={s}s)", s=settings.simulation_tick_seconds)
    while True:
        await asyncio.sleep(settings.simulation_tick_seconds)
        try:
            db = SessionLocal()
            try:
                simulation_service.tick(db)
                await ws_manager.broadcast_state(db)
            finally:
                db.close()
        except Exception:
            logger.exception("Simulation tick failed")



@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _bootstrap_db()
    if IS_SERVERLESS:
        logger.info("Running in serverless mode — background loop disabled")
    else:
        asyncio.create_task(_simulation_loop())
    logger.info("Sentinel Command API ready (serverless={s})", s=IS_SERVERLESS)
    yield
    logger.info("Sentinel Command API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sentinel Command API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin.router)
    app.include_router(incidents.router)
    app.include_router(agents.router)
    app.include_router(analytics.router)
    app.include_router(geocoding.router)

    @app.middleware("http")
    async def lazy_bootstrap(request, call_next):
        if not getattr(app.state, "db_ready", False):
            try:
                _bootstrap_db()
                app.state.db_ready = True
            except Exception:
                pass
        return await call_next(request)

    return app


app = create_app()
