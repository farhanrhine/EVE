from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from app.db.models import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: int = Field(..., gt=0, description="Booking ID to pay for")
    # For reproducible testing or simulation override:
    simulate_status: Optional[PaymentStatus] = Field(
        default=PaymentStatus.SUCCESS,
        description="Simulated outcome: SUCCESS or FAILED. Defaults to SUCCESS.",
    )


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    provider_reference_id: str
    status: PaymentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookData(BaseModel):
    provider_reference_id: str = Field(..., min_length=1)
    booking_id: int = Field(..., gt=0)
    status: PaymentStatus
    amount: Optional[float] = Field(None, gt=0)


class WebhookPayload(BaseModel):
    event_id: str = Field(..., min_length=1, description="Unique event identifier from payment provider")
    event_type: str = Field(..., min_length=1, description="Event type name, e.g. payment.success")
    data: WebhookData


class WebhookResponse(BaseModel):
    status: str
    event_id: str
    detail: Optional[str] = None
