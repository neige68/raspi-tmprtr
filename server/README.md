# raspi-tmprtr-server

Raspberry Pi 温度センサーデータを受信・保存するサーバー。FastAPI + MariaDB で構成。

## 環境構築

```bash
uv sync
cp dot.env .env  # DATABASE_URL と TOTP_SECRET を設定する
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

### 手動実行

```bash
uv run python monitor.py
uv run python daily_report.py
```

## データ送信テスト

```bash
# TOTP コードを生成してから curl で送信
python -c "import pyotp; print(pyotp.TOTP('シークレット').now())"
curl -X POST http://127.0.0.1:8000/sensor_data \
    -H "Content-Type: application/json" \
    -H "X-TOTP-Code: <TOTP コード>" \
    -d '{"sensor_id": "SENSOR01", "temperature": 23.456}'
```
