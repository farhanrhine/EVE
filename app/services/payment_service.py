import uuid
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import Booking, BookingStatus, Payment, PaymentStatus, WebhookEvent
from app.schemas.payment import WebhookPayload


def process_payment(
    db: Session,
    booking_id: int,
    user_id: int,
    simulate_status: PaymentStatus = PaymentStatus.SUCCESS,
) -> Payment:
    """
    Process payment with concurrency protection using SELECT ... FOR UPDATE row-level lock.
    Rejects payment on already CONFIRMED/CANCELLED/FAILED bookings with 409 Conflict.
    """
    # 1. Lock the booking row before inspecting or modifying status
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found",
        )

    if booking.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to pay for this booking",
        )

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot process payment for booking with status '{booking.status.value}'. "
                "Only PENDING bookings can be paid."
            ),
        )

    # 2. Simulate payment reference and record payment
    provider_ref = f"pay_{uuid.uuid4().hex[:16]}"
    payment = Payment(
        booking_id=booking.id,
        provider_reference_id=provider_ref,
        status=simulate_status,
    )
    db.add(payment)

    # 3. Apply state transition
    previous_booking_status = booking.status
    if simulate_status == PaymentStatus.SUCCESS:
        booking.status = BookingStatus.CONFIRMED
    else:
        booking.status = BookingStatus.FAILED

    db.commit()
    db.refresh(payment)
    db.refresh(booking)

    logger.info(
        "Payment processed",
        extra={
            "extra_data": {
                "event": "payment_processed",
                "payment_id": payment.id,
                "provider_reference_id": payment.provider_reference_id,
                "booking_id": booking.id,
                "user_id": user_id,
                "payment_status": payment.status.value,
                "booking_status_before": previous_booking_status.value,
                "booking_status_after": booking.status.value,
            }
        },
    )

    return payment


def process_webhook(db: Session, payload: WebhookPayload) -> dict:
    """
    Process incoming payment webhook idempotently.
    - Uses unique constraint on webhook_events(event_id)
    - Returns 200 on duplicate event without side effects
    - Handles unknown bookings gracefully (logs + returns 200)
    - Enforces booking state machine
    """
    event_id = payload.event_id
    payload_dict = payload.model_dump(mode="json")
    data = payload.data

    # Step 1: Attempt to register the webhook event
    webhook_event = WebhookEvent(
        event_id=event_id,
        payload=payload_dict,
    )
    db.add(webhook_event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info(
            "Duplicate webhook event ignored (idempotent)",
            extra={
                "extra_data": {
                    "event": "webhook_duplicate_ignored",
                    "event_id": event_id,
                }
            },
        )
        return {
            "status": "already_processed",
            "event_id": event_id,
            "detail": "Duplicate event ID ignored with no state change",
        }

    # Step 2: Look up booking and lock row
    booking = (
        db.query(Booking)
        .filter(Booking.id == data.booking_id)
        .with_for_update()
        .first()
    )

    if not booking:
        # Edge case: unknown booking reference -> log + 200 (don't break provider retry loop)
        db.commit()
        logger.warning(
            "Webhook received for unknown booking",
            extra={
                "extra_data": {
                    "event": "webhook_unknown_booking",
                    "event_id": event_id,
                    "booking_id": data.booking_id,
                }
            },
        )
        return {
            "status": "ignored_unknown_reference",
            "event_id": event_id,
            "detail": f"Booking ID {data.booking_id} not found; event recorded.",
        }

    # Step 3: Find or create Payment record
    payment = (
        db.query(Payment)
        .filter(Payment.provider_reference_id == data.provider_reference_id)
        .first()
    )

    if payment:
        payment.status = data.status
    else:
        payment = Payment(
            booking_id=booking.id,
            provider_reference_id=data.provider_reference_id,
            status=data.status,
        )
        db.add(payment)

    # Step 4: Apply Booking state machine guard
    # Legal: PENDING -> CONFIRMED, PENDING -> FAILED, PENDING/CONFIRMED -> CANCELLED
    # Anything else is a no-op, not a 500
    state_changed = False
    if booking.status == BookingStatus.PENDING:
        if data.status == PaymentStatus.SUCCESS:
            booking.status = BookingStatus.CONFIRMED
            state_changed = True
        elif data.status == PaymentStatus.FAILED:
            booking.status = BookingStatus.FAILED
            state_changed = True
    else:
        logger.info(
            "Webhook state transition no-op: current booking status final or transition illegal",
            extra={
                "extra_data": {
                    "event": "webhook_transition_noop",
                    "event_id": event_id,
                    "booking_id": booking.id,
                    "current_status": booking.status.value,
                    "incoming_payment_status": data.status.value,
                }
            },
        )

    db.commit()

    logger.info(
        "Webhook processed successfully",
        extra={
            "extra_data": {
                "event": "webhook_processed",
                "event_id": event_id,
                "booking_id": booking.id,
                "payment_status": data.status.value,
                "booking_status": booking.status.value,
                "state_changed": state_changed,
            }
        },
    )

    return {
        "status": "processed",
        "event_id": event_id,
        "detail": "Webhook event processed successfully",
    }
