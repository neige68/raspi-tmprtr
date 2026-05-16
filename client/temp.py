#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from w1thermsensor import W1ThermSensor

# 接続されているすべてのセンサーを取得
sensors = W1ThermSensor.get_available_sensors()

print(f"検出されたセンサー数: {len(sensors)}")

for i, sensor in enumerate(sensors, 1):
    # sensor.id で固有のID（シリアル番号）を取得できます
    temperature = sensor.get_temperature()
    print(f"センサー {i} [ID: {sensor.id}]: {temperature:.2f} °C")
