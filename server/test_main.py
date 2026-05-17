from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from database import get_db
from main import app, verify_totp


def override_get_db():
    yield MagicMock()


def override_verify_totp():
    pass


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[verify_totp] = override_verify_totp

client = TestClient(app)

def test_read_root():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json() == {"Hello": "World"}

def test_post_sensor_data():
    res = client.post("/sensor_data", json={
        "sensor_id": "SENSOR01",
        "temperature": 23.456,
    })
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

def test_post_sensor_data_invalid_id_too_long():
    res = client.post("/sensor_data", json={
        "sensor_id": "A" * 31,
        "temperature": 20.0,
    })
    assert res.status_code == 422

def test_post_sensor_data_missing_field():
    res = client.post("/sensor_data", json={
        "sensor_id": "SENSOR01",
    })
    assert res.status_code == 422
