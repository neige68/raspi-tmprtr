#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from gpiozero import CPUTemperature
from w1thermsensor import W1ThermSensor


def read_cpu_temperature():
    """CPU温度を取得"""
    cpu = CPUTemperature()
    return {
        'id': 'cpu',
        'temperature': cpu.temperature,
    }


def read_ds18b20_sensors():
    """DS18B20 温度センサーをすべて読み取る"""
    sensors = W1ThermSensor.get_available_sensors()
    readings = []

    for sensor in sensors:
        readings.append({
            'id': sensor.id,
            'temperature': sensor.get_temperature(),
        })

    return readings


def main():
    # CPU温度を読み取る
    cpu_reading = read_cpu_temperature()
    print(f"CPU温度 [{cpu_reading['id']}]: {cpu_reading['temperature']:.2f} °C")

    # DS18B20 センサーを読み取る
    ds18b20_readings = read_ds18b20_sensors()
    print(f"\n検出されたセンサー数: {len(ds18b20_readings)}")

    for reading in ds18b20_readings:
        print(f"センサー [ID: {reading['id']}]: {reading['temperature']:.2f} °C")


if __name__ == "__main__":
    main()
