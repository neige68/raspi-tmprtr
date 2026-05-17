#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""センサー読み取りモジュール。MOCK_SENSORS=1 でスタブ動作する。"""
import os
from dotenv import load_dotenv

load_dotenv()

MOCK_SENSORS = os.environ.get('MOCK_SENSORS', '0') == '1'


def read_cpu_temperature() -> dict:
    """CPU温度を取得する。"""
    if MOCK_SENSORS:
        return {'id': 'cpu', 'temperature': 45.0}

    # GPIOZERO_PIN_FACTORY=mock が設定されていれば gpiozero 自体もモック動作する
    from gpiozero import CPUTemperature
    cpu = CPUTemperature()
    return {'id': 'cpu', 'temperature': cpu.temperature}


def read_ds18b20_sensors() -> list[dict]:
    """DS18B20 温度センサーをすべて読み取る。"""
    if MOCK_SENSORS:
        return [
            {'id': 'stub-sensor-01', 'temperature': 23.5},
            {'id': 'stub-sensor-02', 'temperature': 24.1},
        ]

    from w1thermsensor import W1ThermSensor
    sensors = W1ThermSensor.get_available_sensors()
    return [
        {'id': sensor.id, 'temperature': sensor.get_temperature()}
        for sensor in sensors
    ]


def read_all_sensors() -> list[dict]:
    """CPU および DS18B20 全センサーの読み取り結果をまとめて返す。"""
    return [read_cpu_temperature()] + read_ds18b20_sensors()
