# raspi-tmprtr-server

Raspberry Pi 温度センサーデータを受信・保存するサーバー。FastAPI + MariaDB で構成。

> 詳細なセットアップ手順はリポジトリルートの [README.md](../README.md) を参照。

## 環境構築

```bash
uv sync
cp dot.env .env  # DATABASE_URL / TOTP_SECRET / SLACK_TOKEN / SLACK_CHANNEL / OWM_API_KEY を設定する
```

## 起動

```bash
# 開発サーバー（ホットリロード有効）
uv run uvicorn main:app --reload

# 本番サーバー
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## テスト

```bash
uv run pytest
```

## 自動起動設定（systemd）

`/etc/systemd/system/raspi-tmprtr.service` を作成する：

```ini
[Unit]
Description=raspi-tmprtr server
After=network.target mysql.service

[Service]
User=<your-username>
WorkingDirectory=/home/<your-username>/raspi-tmprtr/server
ExecStart=/home/<your-username>/raspi-tmprtr/server/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

有効化・起動：

```bash
sudo systemctl daemon-reload
sudo systemctl enable raspi-tmprtr
sudo systemctl start raspi-tmprtr
```

ログ確認：

```bash
journalctl -u raspi-tmprtr -f
```

## cron 登録

cron は PATH が最小限のため、各 crontab ファイル内で `uv` のインストール先を含む PATH を設定している。
`<your-username>` を実際のユーザー名に置き換えてから登録すること。
`uv` を別の場所にインストールした場合は PATH も修正すること。

### モニター（毎分実行）

```bash
# 初回登録
crontab monitor.crontab

# 既存の crontab に追記する場合
crontab -l | cat - monitor.crontab | crontab -
```

ログ確認：

```bash
journalctl -t raspi-monitor -f
```

### 日次レポート（毎日 8:00）

```bash
# 初回登録
crontab daily_report.crontab

# 既存の crontab に追記する場合
crontab -l | cat - daily_report.crontab | crontab -
```

ログ確認：

```bash
journalctl -t raspi-daily-report -f
```

### 推定屋外気温取得（5 分ごと）

OpenWeatherMap から気温を取得し `EstimatedOutdoor` として DB に保存する。  
事前に `.env` の `OWM_API_KEY`（[openweathermap.org](https://openweathermap.org/api) で取得）と `OWM_CITY` を設定すること。

```bash
# 初回登録
crontab outdoor_temp.crontab

# 既存の crontab に追記する場合
crontab -l | cat - outdoor_temp.crontab | crontab -
```

ログ確認：

```bash
journalctl -t raspi-outdoor-temp -f
```

### 手動実行

```bash
uv run python monitor.py
uv run python daily_report.py
uv run python outdoor_temp.py
```

## Slack 通知テスト

`.env` の `SLACK_TOKEN` / `SLACK_CHANNEL` が正しく設定されているか確認する：

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv(); from slack_notify import slack_post; slack_post('テスト通知: raspi-tmprtr Slack 設定確認')"
```

成功すると `Slack 送信成功` とログに出力され、指定チャンネルにメッセージが届く。

## データ送信テスト

```bash
# TOTP コードを生成してから curl で送信
uv run python -c "import pyotp; print(pyotp.TOTP('シークレット').now())"
curl -X POST http://127.0.0.1:8000/sensor_data \
    -H "Content-Type: application/json" \
    -H "X-TOTP-Code: <TOTP コード>" \
    -d '{"sensor_id": "SENSOR01", "temperature": 23.456}'
```
