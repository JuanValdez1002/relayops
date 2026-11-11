
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any]

    @field_validator("event_type", "source", mode="before")
    @classmethod
    def strip_required_strings(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    source: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    retry_count: int
    last_error: str | None
    next_retry_at: datetime | None
    processing_started_at: datetime | None


class EventStatusUpdate(BaseModel):
    status: Literal[
        "processing",
        "processed",
        "failed",
    ]
