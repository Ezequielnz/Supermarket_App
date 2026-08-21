import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_success():
    fake_user = MagicMock()
    fake_user.id = str(uuid.uuid4())
    fake_user.created_at = "2026-08-20T00:00:00Z"
    fake_result = MagicMock()
    fake_result.user = fake_user

    with patch("app.services.auth_service.get_supabase") as mock_get_supabase:
        mock_get_supabase.return_value.auth.admin.create_user.return_value = fake_result
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "full_name": "Test User",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "test@example.com"
    assert body["full_name"] == "Test User"


def test_register_duplicate_email():
    with patch("app.services.auth_service.get_supabase") as mock_get_supabase:
        mock_get_supabase.return_value.auth.admin.create_user.side_effect = Exception(
            "User already registered"
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "full_name": "Test User",
            },
        )

    assert response.status_code == 409


def test_register_invalid_payload():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short", "full_name": ""},
    )
    assert response.status_code == 422
