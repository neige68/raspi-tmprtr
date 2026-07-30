#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from unittest.mock import MagicMock
import pytest
import sensors


# ── モックパス（MOCK_SENSORS=1）のテスト ──────────────────────────────────

class TestMockPath:
    def test_cpu_temperature(self, monkeypatch):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', True)
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'raspberrypi')
        result = sensors.read_cpu_temperature()
        assert result == {'id': 'cpu', 'temperature': 45.0}

    def test_cpu_temperature_other_host(self, monkeypatch):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', True)
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'pi2')
        result = sensors.read_cpu_temperature()
        assert result == {'id': 'pi2_cpu', 'temperature': 45.0}

    def test_ds18b20_sensors(self, monkeypatch):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', True)
        result = sensors.read_ds18b20_sensors()
        assert len(result) == 2
        assert result[0] == {'id': 'stub-sensor-01', 'temperature': 23.5}
        assert result[1] == {'id': 'stub-sensor-02', 'temperature': 24.1}

    def test_read_all_sensors(self, monkeypatch):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', True)
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'raspberrypi')
        result = sensors.read_all_sensors()
        # CPU + DS18B20 x2
        assert len(result) == 3
        assert result[0]['id'] == 'cpu'


class TestCpuSensorId:
    def test_default_host(self, monkeypatch):
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'raspberrypi')
        assert sensors.cpu_sensor_id() == 'cpu'

    def test_default_host_fqdn(self, monkeypatch):
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'raspberrypi.local')
        assert sensors.cpu_sensor_id() == 'cpu'

    def test_other_host(self, monkeypatch):
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'pi2')
        assert sensors.cpu_sensor_id() == 'pi2_cpu'


# ── 本番パス（ハードウェアライブラリを sys.modules で差し替え）のテスト ──

@pytest.fixture
def fake_gpiozero(monkeypatch):
    """gpiozero.CPUTemperature を偽モジュールで差し替える。"""
    mock_cpu_instance = MagicMock()
    mock_cpu_instance.temperature = 52.3
    mock_module = MagicMock()
    mock_module.CPUTemperature.return_value = mock_cpu_instance
    monkeypatch.setitem(sys.modules, 'gpiozero', mock_module)
    return mock_module


@pytest.fixture
def fake_w1thermsensor(monkeypatch):
    """w1thermsensor.W1ThermSensor を偽モジュールで差し替える。"""
    def make_sensor(sid, temp):
        s = MagicMock()
        s.id = sid
        s.get_temperature.return_value = temp
        return s

    mock_module = MagicMock()
    mock_module.W1ThermSensor.get_available_sensors.return_value = [
        make_sensor('real-sensor-01', 22.5),
        make_sensor('real-sensor-02', 23.1),
    ]
    monkeypatch.setitem(sys.modules, 'w1thermsensor', mock_module)
    return mock_module


class TestRealPath:
    def test_cpu_temperature(self, monkeypatch, fake_gpiozero):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', False)
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'raspberrypi')
        result = sensors.read_cpu_temperature()
        assert result == {'id': 'cpu', 'temperature': 52.3}

    def test_cpu_temperature_other_host(self, monkeypatch, fake_gpiozero):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', False)
        monkeypatch.setattr(sensors.socket, 'gethostname', lambda: 'pi2')
        result = sensors.read_cpu_temperature()
        assert result == {'id': 'pi2_cpu', 'temperature': 52.3}

    def test_ds18b20_sensors(self, monkeypatch, fake_w1thermsensor):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', False)
        result = sensors.read_ds18b20_sensors()
        assert result == [
            {'id': 'real-sensor-01', 'temperature': 22.5},
            {'id': 'real-sensor-02', 'temperature': 23.1},
        ]

    def test_ds18b20_no_sensors(self, monkeypatch, fake_w1thermsensor):
        monkeypatch.setattr(sensors, 'MOCK_SENSORS', False)
        fake_w1thermsensor.W1ThermSensor.get_available_sensors.return_value = []
        result = sensors.read_ds18b20_sensors()
        assert result == []
