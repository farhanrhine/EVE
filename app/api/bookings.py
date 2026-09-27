from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Booking, User
from app.schemas.booking import BookingCreate, BookingResponse
from app.services.booking_service import (
    create_booking,
    get_booking,
    list_bookings,
    cancel_booking,
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_new_booking(
    booking_in: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    return create_booking(
        db=db,
        user_id=current_user.id,
        test_id=booking_in.test_id,
        appointment_time=booking_in.appointment_time,
    )


@router.get("/", response_model=List[BookingResponse])
def get_user_bookings(
    skip: int = Query(0, ge=0, description="Items to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Booking]:
    bookings, _ = list_bookings(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return bookings


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_by_id(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    return get_booking(db=db, booking_id=booking_id, user_id=current_user.id)


@router.delete("/{booking_id}", response_model=BookingResponse)
def cancel_booking_by_id(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    return cancel_booking(db=db, booking_id=booking_id, user_id=current_user.id)
