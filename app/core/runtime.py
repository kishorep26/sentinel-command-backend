import os
from loguru import logger

# Vercel serverless has no persistent process
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def run_request_tick() -> None:
    """Run a simulation tick on each request when in serverless mode (no background loop)."""
    if not IS_SERVERLESS:
        return
    from app.core.database import SessionLocal
    from app.services import simulation as simulation_service
    try:
        db = SessionLocal()
        try:
            simulation_service.tick(db)
        finally:
            db.close()
    except Exception:
        logger.warning("Request-tick failed (non-fatal)")
