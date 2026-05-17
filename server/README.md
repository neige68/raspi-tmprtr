# raspi-tmprtr-server

Raspberry Pi 温度センサーデータを受信・保存するサーバー。FastAPI + MariaDB で構成。

## 環境構築

```bash
uv sync --dev
cp dot.env .env  # DATABASE_URL と TOTP_SECRET を設定する
```

## 起動

```bash
# 開発サーバー（ホットリロード有効）
uv run uvicorn main:app --reload

# 本番サーバー（descartes 上で実行）
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## テスト

```bash
uv run pytest
```

## 自動起動設定（descartes / systemd）

`/etc/systemd/system/raspi-tmprtr.service` を作成する：

```ini
[Unit]
Description=raspi-tmprtr server
After=network.target mysql.service

[Service]
User=neige
WorkingDirectory=/home/neige/raspi-tmprtr/server
ExecStart=/home/neige/raspi-tmprtr/server/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
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

## データ送信テスト

```bash
# TOTP コードを生成してから curl で送信
python -c "import pyotp; print(pyotp.TOTP('シークレット').now())"
curl -X POST http://127.0.0.1:8000/sensor_data \
    -H "Content-Type: application/json" \
    -H "X-TOTP-Code: <TOTP コード>" \
    -d '{"sensor_id": "SENSOR01", "temperature": 23.456}'
```
