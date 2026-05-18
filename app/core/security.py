from fastapi import Header, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address)


async def verify_api_key(x_api_key: str = Header(default="")):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
