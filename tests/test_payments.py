import concurrent.futures
from datetime import datetime, timedelta, timezone
from fastapi import status


def test_payment_happy_path_success(client, auth_user, sample_test):
    # 1. Create booking (starts in PENDING)
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    assert booking_resp.status_code == status.HTTP_201_CREATED
    booking_id = booking_resp.json()["id"]
    assert booking_resp.json()["status"] == "PENDING"

    # 2. Process payment (SUCCESS)
    pay_resp = client.post(
        "/payments/",
        headers=auth_user["headers"],
        json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
    )
    assert pay_resp.status_code == status.HTTP_201_CREATED
    pay_data = pay_resp.json()
    assert pay_data["booking_id"] == booking_id
    assert pay_data["status"] == "SUCCESS"
    assert "provider_reference_id" in pay_data

    # 3. Check booking status transitioned to CONFIRMED
    get_resp = client.get(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["status"] == "CONFIRMED"


def test_payment_failure_flow(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    # Process payment with simulated failure
    pay_resp = client.post(
        "/payments/",
        headers=auth_user["headers"],
        json={"booking_id": booking_id, "simulate_status": "FAILED"},
    )
    assert pay_resp.status_code == status.HTTP_201_CREATED
    assert pay_resp.json()["status"] == "FAILED"

    # Check booking transitioned to FAILED
    get_resp = client.get(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert get_resp.json()["status"] == "FAILED"


def test_payment_on_already_confirmed_booking_returns_409(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    # First payment succeeds
    pay_1 = client.post(
        "/payments/",
        headers=auth_user["headers"],
        json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
    )
    assert pay_1.status_code == status.HTTP_201_CREATED

    # Second payment attempt on confirmed booking must return 409
    pay_2 = client.post(
        "/payments/",
        headers=auth_user["headers"],
        json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
    )
    assert pay_2.status_code == status.HTTP_409_CONFLICT
    assert "Cannot process payment" in pay_2.json()["detail"]


def test_payment_on_cancelled_booking_returns_409(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    # Cancel booking
    cancel_resp = client.delete(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert cancel_resp.status_code == status.HTTP_200_OK

    # Attempt payment on cancelled booking
    pay_resp = client.post(
        "/payments/",
        headers=auth_user["headers"],
        json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
    )
    assert pay_resp.status_code == status.HTTP_409_CONFLICT


def test_payment_on_other_user_booking_forbidden(client, auth_user, second_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    # second_user attempts payment on auth_user's booking
    pay_resp = client.post(
        "/payments/",
        headers=second_user["headers"],
        json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
    )
    assert pay_resp.status_code == status.HTTP_403_FORBIDDEN


def test_payment_on_nonexistent_booking_returns_404(client, auth_user):
    pay_resp = client.post(
        "/payments/",
        headers=auth_user["headers"],
        json={"booking_id": 99999, "simulate_status": "SUCCESS"},
    )
    assert pay_resp.status_code == status.HTTP_404_NOT_FOUND


def test_concurrent_payments_only_one_succeeds(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = booking_resp.json()["id"]

    def make_payment():
        return client.post(
            "/payments/",
            headers=auth_user["headers"],
            json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
        )

    # Trigger concurrent payment requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(make_payment)
        f2 = executor.submit(make_payment)
        r1 = f1.result()
        r2 = f2.result()

    status_codes = sorted([r1.status_code, r2.status_code])
    # Exactly one should succeed (201) and one should fail (409 Conflict)
    assert status_codes == [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
