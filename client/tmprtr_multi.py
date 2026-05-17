#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sensors import read_cpu_temperature, read_ds18b20_sensors


def main():
    cpu_reading = read_cpu_temperature()
    print(f"CPU温度 [{cpu_reading['id']}]: {cpu_reading['temperature']:.2f} °C")

    ds18b20_readings = read_ds18b20_sensors()
    print(f"\n検出されたセンサー数: {len(ds18b20_readings)}")

    for reading in ds18b20_readings:
        print(f"センサー [ID: {reading['id']}]: {reading['temperature']:.2f} °C")


if __name__ == "__main__":
    main()
