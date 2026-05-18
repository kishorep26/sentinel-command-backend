import os
import sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import app
except Exception as e:
    # Surface the real import error so we can see it in the Vercel response
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.get("/{path:path}")
    async def error_handler(path: str):
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )
