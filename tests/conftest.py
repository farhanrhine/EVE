import os
import sys

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base, get_db
from app.db.models import User, DiagnosticCentre, DiagnosticTest, Booking, BookingStatus
from app.core.security import hash_password, create_access_token
from app.main import app

# In-memory SQLite with StaticPool so all connections share the same in-memory DB during tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_user(db_session):
    password = "password123"
    user = User(
        email="testuser@example.com",
        password_hash=hash_password(password),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "user": user,
        "email": user.email,
        "password": password,
        "headers": headers,
        "token": token,
    }


@pytest.fixture
def second_user(db_session):
    password = "password123"
    user = User(
        email="seconduser@example.com",
        password_hash=hash_password(password),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "user": user,
        "email": user.email,
        "password": password,
        "headers": headers,
        "token": token,
    }


@pytest.fixture
def sample_test(db_session):
    centre = DiagnosticCentre(
        name="Apex Diagnostics",
        location="Indiranagar, Bangalore",
    )
    db_session.add(centre)
    db_session.flush()

    test = DiagnosticTest(
        centre_id=centre.id,
        name="Complete Blood Count",
        price=500.0,
    )
    db_session.add(test)
    db_session.commit()
    db_session.refresh(centre)
    db_session.refresh(test)

    return {
        "centre": centre,
        "test": test,
    }
