from datetime import datetime
from typing import Tuple, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import Booking, BookingStatus, DiagnosticTest, DiagnosticCentre


def create_booking(
    db: Session,
    user_id: int,
    test_id: int,
    appointment_time: datetime,
) -> Booking:
    test = db.query(DiagnosticTest).filter(DiagnosticTest.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic test with ID {test_id} not found",
        )

    booking = Booking(
        user_id=user_id,
        test_id=test.id,
        centre_id=test.centre_id,
        appointment_time=appointment_time,
        amount=test.price,
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    logger.info(
        "Booking created",
        extra={
            "extra_data": {
                "event": "booking_created",
                "booking_id": booking.id,
                "user_id": user_id,
                "test_id": test.id,
                "centre_id": test.centre_id,
                "amount": float(booking.amount),
                "status": booking.status.value,
            }
        },
    )
    return booking


def get_booking(db: Session, booking_id: int, user_id: int) -> Booking:
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found",
        )
    if booking.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this booking",
        )
    return booking


def list_bookings(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Booking], int]:
    query = db.query(Booking).filter(Booking.user_id == user_id)
    total = query.count()
    items = (
        query.order_by(Booking.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def cancel_booking(db: Session, booking_id: int, user_id: int) -> Booking:
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
            detail="You are not authorized to cancel this booking",
        )

    # State machine: PENDING/CONFIRMED -> CANCELLED
    # Anything else is a no-op, not a 500
    if booking.status in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
        previous_status = booking.status
        booking.status = BookingStatus.CANCELLED
        db.commit()
        db.refresh(booking)
        logger.info(
            "Booking cancelled",
            extra={
                "extra_data": {
                    "event": "booking_cancelled",
                    "booking_id": booking.id,
                    "user_id": user_id,
                    "previous_status": previous_status.value,
                    "new_status": booking.status.value,
                }
            },
        )
    else:
        logger.info(
            "Booking cancellation no-op due to state machine rule",
            extra={
                "extra_data": {
                    "event": "booking_cancel_noop",
                    "booking_id": booking.id,
                    "status": booking.status.value,
                }
            },
        )

    return booking
