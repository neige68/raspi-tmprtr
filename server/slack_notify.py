"""Slack 通知ヘルパー。"""
import os

import requests
from loguru import logger


def slack_post(message: str) -> None:
    token = os.environ.get('SLACK_TOKEN', '')
    channel = os.environ.get('SLACK_CHANNEL', '')
    if not token or not channel:
        logger.warning("SLACK_TOKEN または SLACK_CHANNEL が未設定のため Slack 通知をスキップします")
        return
    resp = requests.post(
        'https://slack.com/api/chat.postMessage',
        data={'token': token, 'channel': channel, 'text': message},
        timeout=10,
    )
    data = resp.json()
    if data.get('ok'):
        logger.info("Slack 送信成功")
    else:
        logger.error(f"Slack 送信失敗: {data.get('error')}")
