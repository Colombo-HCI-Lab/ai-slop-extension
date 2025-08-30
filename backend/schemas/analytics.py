"""Analytics schemas (consolidated)."""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class UserInitRequest(BaseModel):
    """Request to initialize a user (server generates ID)."""

    browser_info: Dict[str, Any] = Field(..., description="Browser and environment information")
    timezone: str = Field(..., description="User timezone")
    locale: str = Field(..., description="User locale")
    client_ip: Optional[str] = Field(None, description="Client IP address for geolocation")


class UserInitResponse(BaseModel):
    """Response from user initialization."""

    user_id: str = Field(..., description="Internal user ID")
    experiment_groups: List[str] = Field(default_factory=list, description="A/B test groups")
