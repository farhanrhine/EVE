import uuid
from datetime import datetime, timedelta, timezone
from fastapi import status
from app.db.models import Payment, WebhookEvent, BookingStatus


def test_webhook_happy_path_confirms_booking(client, auth_user, sample_test, db_session):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    event_id = f"evt_{uuid.uuid4().hex}"
    provider_ref = f"pay_{uuid.uuid4().hex}"

    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.success",
        "data": {
            "booking_id": booking_id,
            "provider_reference_id": provider_ref,
            "status": "SUCCESS",
            "amount": 500.0,
        },
    }

    response = client.post("/payments/webhook/", json=webhook_payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "processed"
    assert response.json()["event_id"] == event_id

    # Verify booking status transitioned to CONFIRMED
    booking_check = client.get(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert booking_check.json()["status"] == "CONFIRMED"

    # Verify payment row created
    payment = db_session.query(Payment).filter(Payment.provider_reference_id == provider_ref).first()
    assert payment is not None
    assert payment.status == "SUCCESS"
    assert payment.booking_id == booking_id


def test_webhook_idempotency_duplicate_event_id(client, auth_user, sample_test, db_session):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    event_id = f"evt_idempotent_{uuid.uuid4().hex}"
    provider_ref = f"pay_{uuid.uuid4().hex}"

    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.success",
        "data": {
            "booking_id": booking_id,
            "provider_reference_id": provider_ref,
            "status": "SUCCESS",
            "amount": 500.0,
        },
    }

    # First webhook submission
    resp1 = client.post("/payments/webhook/", json=webhook_payload)
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["status"] == "processed"

    # Count payments before duplicate
    count_payments_1 = db_session.query(Payment).filter(Payment.booking_id == booking_id).count()
    assert count_payments_1 == 1

    # Second webhook submission with identical event_id
    resp2 = client.post("/payments/webhook/", json=webhook_payload)
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["status"] == "already_processed"
    assert "Duplicate event" in resp2.json()["detail"]

    # Verify no duplicate Payment rows were created
    count_payments_2 = db_session.query(Payment).filter(Payment.booking_id == booking_id).count()
    assert count_payments_2 == 1

    # Verify only one WebhookEvent row exists
    event_count = db_session.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).count()
    assert event_count == 1


def test_webhook_unknown_booking_reference_handled_gracefully(client):
    event_id = f"evt_unknown_{uuid.uuid4().hex}"
    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.success",
        "data": {
            "booking_id": 99999,
            "provider_reference_id": "pay_nonexistent",
            "status": "SUCCESS",
            "amount": 500.0,
        },
    }

    # Provider retry loops should receive 200 without throwing 500
    response = client.post("/payments/webhook/", json=webhook_payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ignored_unknown_reference"


def test_webhook_schema_validation_failure_returns_400(client):
    # Malformed payload missing event_id and invalid structure
    malformed_payload = {
        "event_type": "payment.success",
        "data": {"something": "invalid"},
    }
    response = client.post("/payments/webhook/", json=malformed_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_webhook_state_machine_guard_cannot_corrupt_cancelled_booking(
    client, auth_user, sample_test, db_session
):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    # Cancel booking first
    cancel_resp = client.delete(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Out-of-order webhook arrives attempting to mark it SUCCESS
    event_id = f"evt_out_of_order_{uuid.uuid4().hex}"
    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.success",
        "data": {
            "booking_id": booking_id,
            "provider_reference_id": f"pay_{uuid.uuid4().hex}",
            "status": "SUCCESS",
            "amount": 500.0,
        },
    }
    response = client.post("/payments/webhook/", json=webhook_payload)
    assert response.status_code == status.HTTP_200_OK

    # Booking must STILL be CANCELLED (state machine preserved)
    booking_check = client.get(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert booking_check.json()["status"] == "CANCELLED"
