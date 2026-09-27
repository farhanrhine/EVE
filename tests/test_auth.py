import pytest
from fastapi import status


def test_signup_success(client):
    response = client.post(
        "/auth/signup",
        json={"email": "newuser@example.com", "password": "securepassword123"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_signup_duplicate_email(client, auth_user):
    response = client.post(
        "/auth/signup",
        json={"email": auth_user["email"], "password": "newpassword123"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]


def test_signup_invalid_data(client):
    # Short password
    response = client.post(
        "/auth/signup",
        json={"email": "valid@example.com", "password": "123"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Invalid email
    response = client.post(
        "/auth/signup",
        json={"email": "not-an-email", "password": "securepassword123"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_login_success(client, auth_user):
    response = client.post(
        "/auth/login",
        json={"email": auth_user["email"], "password": auth_user["password"]},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, auth_user):
    response = client.post(
        "/auth/login",
        json={"email": auth_user["email"], "password": "wrongpassword"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_nonexistent_user(client):
    response = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "somepassword"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_route_rejects_missing_token(client):
    response = client.get("/bookings/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_route_rejects_invalid_token(client):
    response = client.get("/bookings/", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
