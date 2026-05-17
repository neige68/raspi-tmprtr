#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

import pyotp
import requests
from sensors import read_all_sensors, read_cpu_temperature, read_ds18b20_sensors


def post_sensor_data(reading: dict) -> bool:
    """センサーデータを SERVER_URL へ POST する。成功時 True を返す。"""
    server_url = os.environ.get('SERVER_URL', '')
    totp_secret = os.environ.get('TOTP_SECRET', '')
    if not server_url or not totp_secret:
        return False

    code = pyotp.TOTP(totp_secret).now()
    response = requests.post(
        server_url,
        json={'sensor_id': reading['id'], 'temperature': reading['temperature']},
        headers={'X-TOTP-Code': code},
        timeout=10,
    )
    response.raise_for_status()
    return True


def main():
    cpu_reading = read_cpu_temperature()
    print(f"CPU温度 [{cpu_reading['id']}]: {cpu_reading['temperature']:.2f} °C")

    ds18b20_readings = read_ds18b20_sensors()
    print(f"\n検出されたセンサー数: {len(ds18b20_readings)}")

    for reading in ds18b20_readings:
        print(f"センサー [ID: {reading['id']}]: {reading['temperature']:.2f} °C")

    server_url = os.environ.get('SERVER_URL', '')
    if not server_url:
        print("\nSERVER_URL 未設定のため送信をスキップします")
        return

    print("\nサーバーへ送信中...")
    for reading in read_all_sensors():
        try:
            post_sensor_data(reading)
            print(f"  送信OK: {reading['id']}")
        except Exception as e:
            print(f"  送信失敗: {reading['id']} — {e}")


if __name__ == "__main__":
    main()
