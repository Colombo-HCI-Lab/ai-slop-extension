"""Base schemas and configurations for UUID handling."""

import uuid

from pydantic import BaseModel, ConfigDict


class UUIDBaseModel(BaseModel):
    """Base model with UUID serialization support."""

    model_config = ConfigDict(
        # Allow UUID objects and serialize them as strings in JSON
        json_encoders={
            uuid.UUID: str,
        },
        # Allow arbitrary types for UUID validation
        arbitrary_types_allowed=True,
    )


class TimestampedUUIDModel(UUIDBaseModel):
    """Base model with UUID and timestamp support."""

    model_config = ConfigDict(
        json_encoders={
            uuid.UUID: str,
        },
        arbitrary_types_allowed=True,
        from_attributes=True,  # Allow creating from ORM models
    )
