from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Payment, User
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    WebhookPayload,
    WebhookResponse,
)
from app.services.payment_service import process_payment, process_webhook

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_in: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Payment:
    """
    Simulate payment for a booking with row-level concurrency lock (FOR UPDATE).
    Rejects payment on already CONFIRMED/CANCELLED/FAILED bookings with 409 Conflict.
    """
    return process_payment(
        db=db,
        booking_id=payment_in.booking_id,
        user_id=current_user.id,
        simulate_status=payment_in.simulate_status,
    )


@router.post("/webhook", response_model=WebhookResponse)
@router.post("/webhook/", response_model=WebhookResponse)
def payment_webhook(
    raw_payload: dict = Body(..., description="Webhook event payload from payment provider"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Simulated external provider webhook endpoint.
    - No authentication required
    - Idempotent by event_id
    - Returns 400 on malformed schema
    - Unknown booking reference returns 200 without throwing 500
    """
    try:
        payload = WebhookPayload.model_validate(raw_payload)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid webhook payload schema", "errors": e.errors()},
        )

    return process_webhook(db=db, payload=payload)
