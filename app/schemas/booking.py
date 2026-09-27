from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.db.models import BookingStatus
from app.schemas.centre import DiagnosticCentreResponse, DiagnosticTestResponse


class BookingCreate(BaseModel):
    test_id: int = Field(..., gt=0, description="ID of diagnostic test to book")
    appointment_time: datetime = Field(..., description="Scheduled appointment datetime (must be in the future)")

    @field_validator("appointment_time")
    @classmethod
    def validate_future_time(cls, v: datetime) -> datetime:
        # Normalize timezone if naive
        now = datetime.now(timezone.utc)
        target = v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)
        if target <= now:
            raise ValueError("appointment_time must be in the future")
        return v


class BookingResponse(BaseModel):
    id: int
    user_id: int
    test_id: int
    centre_id: int
    appointment_time: datetime
    amount: float = Field(..., gt=0)
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
    test: Optional[DiagnosticTestResponse] = None
    centre: Optional[DiagnosticCentreResponse] = None

    model_config = ConfigDict(from_attributes=True)


class BookingListResponse(BaseModel):
    items: List[BookingResponse]
    total: int
    skip: int
    limit: int
