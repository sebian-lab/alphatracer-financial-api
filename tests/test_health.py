import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Verify that the health check endpoint returns 200 OK and status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_security_headers():
    """Verify that secure HTTP headers are injected into API responses."""
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "max-age=" in response.headers.get("Strict-Transport-Security", "")

def test_rate_limiting():
    """Verify that repeated logins eventually return 429 Too Many Requests."""
    # Let's perform multiple requests to trigger rate limiting
    # The limit is 5 attempts per 60 seconds.
    responses = []
    for _ in range(6):
        response = client.post("/api/v1/auth/login/json", json={
            "email": "nonexistent@test.com",
            "password": "somepassword"
        })
        responses.append(response)

    # At least the last one should be rate limited (429)
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
