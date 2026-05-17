# raspi-tmprtr-client

Raspberry Pi 温度センサー読み取りクライアント。DS18B20 センサーおよび CPU 温度を取得し、サーバーへ送信する。

## 環境構築

### 開発環境（Hawking WSL）

センサーライブラリは不要。pytest が入る。

```bash
uv sync --dev
cp dot.env .env  # MOCK_SENSORS=1 に設定する
```

### 本番環境（raspi 実機）

```bash
sudo apt install swig python3-dev liblgpio-dev
uv python install 3.13
uv sync --no-dev --extra raspi
cp dot.env .env  # SERVER_URL と TOTP_SECRET を設定する
```

## 実行

```bash
# 開発環境（スタブ値を返す）
uv run python tmprtr_multi.py

# 本番環境（実センサーを読む）
uv run python tmprtr_multi.py
```

## テスト

```bash
uv run pytest
```
