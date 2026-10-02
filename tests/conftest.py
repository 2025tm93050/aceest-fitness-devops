import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    """Fresh app with its own temporary SQLite database for every test."""
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_client(client):
    """Create a standard client and return its JSON representation."""
    response = client.post(
        "/clients",
        json={
            "name": "Arun",
            "age": 28,
            "height": 175,
            "weight": 80,
            "program": "FL",
            "target_weight": 72,
            "target_adherence": 90,
            "membership_end": "2099-12-31",
        },
    )
    assert response.status_code == 201
    return response.get_json()
