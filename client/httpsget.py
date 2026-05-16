#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

try:
    # HTTPS GET リクエストを送信
    response = requests.get("https://www.neige.nu", timeout=5)

    # ステータスコードの確認 (200なら成功)
    print(f"ステータス: {response.status_code}")

    response.raise_for_status()  # エラーがあればここで例外が発生する

    # テキストとして中身を表示
    print(response.text)

except Timeout:
    print("タイムアウトしました。ネットワークを確認してください。")
except ConnectionError:
    print("サーバーに接続できません。URLが正しいか確認してください。")
except requests.exceptions.HTTPError as err:
    print(f"HTTPエラーが発生しました: {err}")
except RequestException as err:
    print(f"予期せぬエラーが発生しました: {err}")
