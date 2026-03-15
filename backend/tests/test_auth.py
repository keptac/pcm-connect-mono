from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_invalid():
    response = client.post("/auth/login", json={"email": "nope", "password": "bad"})
    assert response.status_code == 401
