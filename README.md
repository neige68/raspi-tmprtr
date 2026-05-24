# raspi-tmprtr

Raspberry Pi の温度センサー監視システム。DS18B20 センサーと CPU 温度を定期収集し、グラフ表示・異常監視・Slack 通知を行う。

```
[Raspberry Pi (client)]  ──POST──→  [Linux Server (server)]
  DS18B20 センサー                     FastAPI + MariaDB
  CPU 温度                             gnuplot グラフ
                                       Slack 通知
```

## 機能

- **定期収集**: DS18B20（1-Wire）センサーと CPU 温度を 1 分おきに取得・送信
- **データ保存**: MariaDB にタイムスタンプ付きで蓄積
- **グラフ表示**: gnuplot で指定期間の温度推移グラフを PNG 生成（`GET /graph`）、自動リフレッシュ HTML（`GET /graph/view`）
- **異常監視**: 無通信・高温・低温を検知し、escalation 付きで Slack 通知
- **日次レポート**: 最新値・24h 統計・異常状況を毎朝 Slack に送信
- **TOTP 認証**: RFC 6238 準拠の時刻ベースワンタイムパスワードで POST を保護

## 構成

| ディレクトリ | 役割 | 動作ホスト |
|---|---|---|
| `client/` | センサー読み取り・POST 送信 | Raspberry Pi |
| `server/` | データ受信・保存・グラフ・通知 | Linux サーバー |

## 必要な環境

### server 側

- Python 3.13+（[uv](https://github.com/astral-sh/uv) で管理）
- MariaDB（または MySQL）
- gnuplot
- Slack Bot Token（通知を使う場合）

### client 側

- Raspberry Pi（Raspbian / Raspberry Pi OS）
- Python 3.13+（uv で管理）
- DS18B20 温度センサー（1-Wire 接続）
- `lgpio` / `gpiozero` / `w1thermsensor`

---

## セットアップ

### 1. TOTP シークレットの生成

client と server で共通のシークレットを 1 つ生成する。

```bash
cd server
uv run python -c "import pyotp; print(pyotp.random_base32())"
```

### 2. server のセットアップ

```bash
cd server
uv sync --dev
cp dot.env .env
```

`.env` を編集する：

```
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/dbname
TOTP_SECRET=<上で生成したシークレット>
SLACK_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL=#your-channel-name
```

MariaDB にテーブルを作成する（[スキーマ](#データベーススキーマ)参照）。

開発サーバーを起動する：

```bash
uv run uvicorn main:app --reload
```

本番環境（systemd）での自動起動：

```ini
# /etc/systemd/system/raspi-tmprtr.service
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

```bash
sudo systemctl daemon-reload
sudo systemctl enable raspi-tmprtr
sudo systemctl start raspi-tmprtr
```

### 3. client のセットアップ（Raspberry Pi 実機）

```bash
sudo apt install swig python3-dev liblgpio-dev
cd client
uv python install 3.13
uv sync --no-dev --extra raspi
cp dot.env .env
```

`.env` を編集する：

```
SERVER_URL=http://<server-host>:8000/sensor_data
TOTP_SECRET=<server と同じシークレット>
MOCK_SENSORS=0
```

cron に登録する：

```bash
# 既存の crontab に追記する場合
crontab -l | cat - tmprtr.crontab | crontab -
```

### 4. 監視・日次レポートの cron 登録（server 側）

```bash
# モニター（毎分）
crontab -l | cat - monitor.crontab | crontab -

# 日次レポート（毎日 8:00 JST）
crontab -l | cat - daily_report.crontab | crontab -
```

---

## API

### `POST /sensor_data`

センサーデータを受信して DB に保存する。

**リクエストヘッダー**: `X-TOTP-Code: <TOTP コード>`

**リクエストボディ**:

```json
{"sensor_id": "cpu", "temperature": 50.0}
```

**curl によるテスト**:

```bash
CODE=$(uv run python -c "import pyotp; print(pyotp.TOTP('YOUR_SECRET').now())")
curl -X POST http://localhost:8000/sensor_data \
  -H "Content-Type: application/json" \
  -H "X-TOTP-Code: $CODE" \
  -d '{"sensor_id": "cpu", "temperature": 50.0}'
```

### `GET /graph`

指定期間の温度推移グラフ（PNG）を返す。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `hours` | int | 24 | 表示する過去 N 時間 |
| `sensor` | string | `all` | `all` / `cpu` / `other` |
| `tz` | int | 9 | タイムゾーンオフセット（時）。例: JST=9、UTC=0 |

```bash
curl "http://localhost:8000/graph?hours=48&sensor=cpu&tz=9" -o graph.png
```

### `GET /graph/view`

グラフを 1 分ごとに自動リフレッシュする HTML ページを返す。パラメータは `/graph` と同じ。ブラウザで直接アクセスして使う。

```
http://localhost:8000/graph/view?hours=24&sensor=all&tz=9
```

---

## テスト

```bash
# server
cd server && uv run pytest

# client（MOCK_SENSORS=1 でスタブ動作）
cd client && uv run pytest
```

---

## 開発環境（センサーなし）

Raspberry Pi 実機がなくても `MOCK_SENSORS=1` でテストできる。

```bash
cd client
uv sync --dev
cp dot.env .env   # MOCK_SENSORS=1 に設定
uv run python tmprtr_multi.py
```

---

## データベーススキーマ

```sql
CREATE TABLE tmprtr (
    sensor_id      VARCHAR(30)  NOT NULL,
    event_datetime DATETIME     NOT NULL DEFAULT current_timestamp(),
    tmprtr         DECIMAL(6,3),
    PRIMARY KEY (sensor_id, event_datetime)
);

CREATE TABLE sensors (
    print_order INT(11)      NOT NULL,
    sensor_id   VARCHAR(30)  NOT NULL,
    print_name  VARCHAR(30),
    lower_limit DECIMAL(6,3),
    upper_limit DECIMAL(6,3),
    PRIMARY KEY (print_order)
);

CREATE TABLE notifications (
    id                INT(11)     NOT NULL,
    text              VARCHAR(80) NOT NULL,
    value             DECIMAL(6,3),
    last_ok_event     DATETIME,
    last_ng_event     DATETIME,
    last_notification DATETIME,
    PRIMARY KEY (id)
);

CREATE TABLE notification_intervals (
    id               INT(11) NOT NULL,
    interval_minutes INT(11) NOT NULL,
    PRIMARY KEY (id)
);

-- 初期データ（通知種別）
INSERT INTO notifications (id, text) VALUES
    (1, 'No Data'),
    (2, '高温'),
    (3, '低温');

-- 通知間隔（分）
INSERT INTO notification_intervals (id, interval_minutes) VALUES (1, 60);
```

---

## ライセンス

MIT
