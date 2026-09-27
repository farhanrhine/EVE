from datetime import datetime, timedelta, timezone
from fastapi import status


def test_list_centres(client, sample_test):
    response = client.get("/centres/")
    assert response.status_code == status.HTTP_200_OK
    centres = response.json()
    assert len(centres) >= 1
    assert centres[0]["name"] == sample_test["centre"].name


def test_list_centre_tests(client, sample_test):
    centre_id = sample_test["centre"].id
    response = client.get(f"/centres/{centre_id}/tests")
    assert response.status_code == status.HTTP_200_OK
    tests = response.json()
    assert len(tests) >= 1
    assert tests[0]["name"] == sample_test["test"].name


def test_list_tests_nonexistent_centre(client):
    response = client.get("/centres/99999/tests")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_booking_success(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={
            "test_id": sample_test["test"].id,
            "appointment_time": future_time,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["amount"] == sample_test["test"].price
    assert data["user_id"] == auth_user["user"].id
    assert data["test_id"] == sample_test["test"].id
    assert data["centre_id"] == sample_test["centre"].id


def test_create_booking_nonexistent_test(client, auth_user):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={
            "test_id": 99999,
            "appointment_time": future_time,
        },
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_booking_past_time_fails(client, auth_user, sample_test):
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={
            "test_id": sample_test["test"].id,
            "appointment_time": past_time,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_booking_by_id(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={
            "test_id": sample_test["test"].id,
            "appointment_time": future_time,
        },
    )
    booking_id = create_resp.json()["id"]

    response = client.get(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == booking_id


def test_get_booking_nonexistent(client, auth_user):
    response = client.get("/bookings/99999", headers=auth_user["headers"])
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_other_user_booking_forbidden(client, auth_user, second_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={
            "test_id": sample_test["test"].id,
            "appointment_time": future_time,
        },
    )
    booking_id = create_resp.json()["id"]

    # second_user tries to get auth_user's booking
    response = client.get(f"/bookings/{booking_id}", headers=second_user["headers"])
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_user_bookings(client, auth_user, second_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    client.post(
        "/bookings/",
        headers=second_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )

    response = client.get("/bookings/", headers=auth_user["headers"])
    assert response.status_code == status.HTTP_200_OK
    bookings = response.json()
    assert len(bookings) == 1
    assert bookings[0]["user_id"] == auth_user["user"].id


def test_cancel_booking(client, auth_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = create_resp.json()["id"]

    response = client.delete(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "CANCELLED"

    # Cancelling again is a legal state machine no-op
    repeat_resp = client.delete(f"/bookings/{booking_id}", headers=auth_user["headers"])
    assert repeat_resp.status_code == status.HTTP_200_OK
    assert repeat_resp.json()["status"] == "CANCELLED"


def test_cancel_other_user_booking_forbidden(client, auth_user, second_user, sample_test):
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_resp = client.post(
        "/bookings/",
        headers=auth_user["headers"],
        json={"test_id": sample_test["test"].id, "appointment_time": future_time},
    )
    booking_id = create_resp.json()["id"]

    response = client.delete(f"/bookings/{booking_id}", headers=second_user["headers"])
    assert response.status_code == status.HTTP_403_FORBIDDEN
