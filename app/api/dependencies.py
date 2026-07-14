"""
FastAPI dependencies shared across routes.

Auth tradeoff (flagged deliberately): this is a single static API key
checked on every request, not a full user-account system (no signup,
login, or per-user permissions). That's the right amount of protection
for a single-operator portfolio demo sitting on the public internet —
it stops randoms from running up your Anthropic bill — but it is not
what a real multi-user product would ship. A proper system would swap
this dependency for OAuth2/JWT verification without touching anything
else, since routes.py only depends on this function's signature.
"""
from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_api_key(x_api_key: str = Header(...)) -> None:
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
