"""User and session initialization schemas."""

import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class UserInitRequest(BaseModel):
    """Request to initialize a user (server generates ID)."""

    browser_info: Dict[str, Any] = Field(..., description="Browser and environment information")
    timezone: str = Field(..., description="User timezone")
    locale: str = Field(..., description="User locale")
    client_ip: Optional[str] = Field(None, description="Client IP address for geolocation")


class UserInitResponse(BaseModel):
    """Response from user initialization."""

    user_id: Union[str, uuid.UUID] = Field(..., description="Internal user ID")
    experiment_groups: List[str] = Field(default_factory=list, description="A/B test groups")


class SessionInitRequest(BaseModel):
    """Request to initialize a session for an existing user."""

    user_id: Union[str, uuid.UUID] = Field(..., description="Existing user identifier")
    browser_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Browser info")
    timezone: Optional[str] = Field(None, description="User timezone")
    locale: Optional[str] = Field(None, description="User locale")


class SessionInitResponse(BaseModel):
    """Response from session initialization."""

    session_id: str = Field(..., description="Generated session identifier")
