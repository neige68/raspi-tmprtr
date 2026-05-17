#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch
import pytest
import tmprtr_multi


class TestPostSensorData:
    def test_success(self, monkeypatch):
        monkeypatch.setenv('SERVER_URL', 'http://localhost:8000/sensor_data')
        monkeypatch.setenv('TOTP_SECRET', 'JBSWY3DPEHPK3PXP')

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch('tmprtr_multi.requests.post', return_value=mock_response) as mock_post:
            result = tmprtr_multi.post_sensor_data({'id': 'cpu', 'temperature': 45.0})

        assert result is True
        args, kwargs = mock_post.call_args
        assert args[0] == 'http://localhost:8000/sensor_data'
        assert kwargs['json'] == {'sensor_id': 'cpu', 'temperature': 45.0}
        assert 'X-TOTP-Code' in kwargs['headers']

    def test_no_server_url(self, monkeypatch):
        monkeypatch.delenv('SERVER_URL', raising=False)
        monkeypatch.setenv('TOTP_SECRET', 'JBSWY3DPEHPK3PXP')
        result = tmprtr_multi.post_sensor_data({'id': 'cpu', 'temperature': 45.0})
        assert result is False

    def test_no_totp_secret(self, monkeypatch):
        monkeypatch.setenv('SERVER_URL', 'http://localhost:8000/sensor_data')
        monkeypatch.delenv('TOTP_SECRET', raising=False)
        result = tmprtr_multi.post_sensor_data({'id': 'cpu', 'temperature': 45.0})
        assert result is False
