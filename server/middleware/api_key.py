"""
API Key authentication middleware.
Protects admin/management endpoints with a simple X-API-Key header check.
Student routes remain open — their security comes from BLE TOTP + face verification.
"""

import os
import logging
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "dev-key-change-me")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(_api_key_header)):
    """FastAPI dependency that validates the X-API-Key header."""
    if not api_key or api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key",
        )
    return api_key
