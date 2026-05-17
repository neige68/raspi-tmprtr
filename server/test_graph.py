from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from database import get_db
from main import app

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def make_db_mock(rows, sensor_rows=None):
    """generate_graph が使う DB セッションのモックを返す。"""
    db = MagicMock()

    def query_side_effect(model):
        from models import Sensors, Tmprtr
        q = MagicMock()
        if model is Sensors:
            q.all.return_value = sensor_rows or []
        elif model is Tmprtr:
            filtered = MagicMock()
            filtered.filter.return_value = filtered
            filtered.order_by.return_value = rows
            q.filter.return_value = filtered
        return q

    db.query.side_effect = query_side_effect
    return db


def make_tmprtr(sensor_id, temp, dt=None):
    r = MagicMock()
    r.sensor_id = sensor_id
    r.tmprtr = Decimal(str(temp))
    r.event_datetime = dt or datetime(2025, 1, 1, 12, 0, 0)
    return r


app.dependency_overrides[get_db] = lambda: make_db_mock([])
client = TestClient(app)


class TestGetGraph:
    def test_returns_png(self):
        rows = [make_tmprtr("cpu", 45.0)]
        with patch("main.generate_graph", return_value=FAKE_PNG) as mock_gen:
            res = client.get("/graph")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        mock_gen.assert_called_once()

    def test_hours_and_sensor_params(self):
        with patch("main.generate_graph", return_value=FAKE_PNG) as mock_gen:
            res = client.get("/graph?hours=168&sensor=cpu")
        assert res.status_code == 200
        args, kwargs = mock_gen.call_args
        assert args[1] == 168
        assert args[2] == "cpu"

    def test_no_data_returns_404(self):
        with patch("main.generate_graph", side_effect=ValueError("データなし")):
            res = client.get("/graph")
        assert res.status_code == 404

    def test_invalid_sensor_returns_422(self):
        res = client.get("/graph?sensor=unknown")
        assert res.status_code == 422

    def test_invalid_hours_returns_422(self):
        res = client.get("/graph?hours=0")
        assert res.status_code == 422
