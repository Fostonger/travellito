"""
Yandex Metrica integration for server-side event tracking.
"""
import asyncio
from typing import Optional, Dict, Any

# Need to add httpx to requirements.txt if not already installed
try:
    import httpx
except ImportError:
    httpx = None

from app.core.config import get_settings

# Get settings instance
settings = get_settings()


async def send_metrika_event(
    client_id: str,
    action: str,
    value: Optional[int] = None,
    **extra: Any
) -> None:
    """
    Send an event to Yandex Metrica using the Measurement Protocol.
    
    Args:
        client_id: Visitor's client ID
        action: Event action name
        value: Optional numeric value for the event
        **extra: Any additional parameters to include
    """
    # Skip if httpx not available
    if httpx is None:
        return

    # Skip if no counter ID or token is configured
    if not settings.METRIKA_COUNTER or not settings.METRIKA_MP_TOKEN:
        return
        
    # Build parameters
    params: Dict[str, Any] = {
        "tid": settings.METRIKA_COUNTER,
        "cid": client_id,
        "t": "event",
        "ea": action,
        "ms": settings.METRIKA_MP_TOKEN,
        **extra,
    }
    
    # Add value if provided
    if value is not None:
        params["ev"] = value
    
    try:
        # Use httpx for async HTTP requests
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://mc.yandex.ru/collect", 
                params=params, 
                timeout=2.0
            )
    except Exception as e:
        # Silent fail - don't break app functionality if analytics fails
        print(f"Metrika error: {e}")


def track_async_event(client_id: str, action: str, value: Optional[int] = None, **extra: Any) -> None:
    """
    Fire-and-forget wrapper for send_metrika_event.
    Creates a background task without waiting for completion.
    
    Use this in API handlers to avoid adding latency.
    """
    # Create task but don't wait for it
    asyncio.create_task(send_metrika_event(client_id, action, value, **extra)) 