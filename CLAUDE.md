# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 開発環境

- **作業場所**: Hawking WSL の `~/raspi-tmprtr/`（このリポジトリのローカルクローン）
- **Claude Code**: Hawking WSL 上で動かす（descartes/raspi はメモリ不足）
- **git push 先**: GitHub 経由で descartes（server 用）と raspi（client 用）に同期
- **server の本番環境**: descartes（`~/raspi-tmprtr/`）
- **client の本番環境**: raspi（`~/raspi-tmprtr/`）

開発・テストは Hawking WSL のローカルクローンで完結させ、動作確認後に push する。  
client は `MOCK_SENSORS=1` でスタブ動作するため、Hawking WSL でもテスト可能。  
実センサー（gpiozero / w1thermsensor）の動作確認は raspi 実機でのみ可能。

## プロジェクト概要

Raspberry Pi の温度センサー監視システム。Ruby CGI で書かれた旧リポジトリ `~/raspi` を Python で再構成している。

- **client/**: raspi 上で動作。DS18B20 センサーと CPU 温度を読み取り、サーバーへ POST する。
- **server/**: descartes 上で動作。受信データを MariaDB に保存し、グラフ生成・異常監視・Slack 通知を行う。

## 実行環境

| 役割 | ホスト | アクセス方法 |
|------|--------|-------------|
| client | raspi (Raspberry Pi) | `~/raspi-home/raspi-tmprtr/` (sshfs) |
| server | descartes | `~/descartes/raspi-tmprtr/` (sshfs) |

Claude Code は Hawking WSL 上で動作させる（descartes/raspi ではメモリ不足）。
コードの編集は Hawking WSL 上の sshfs マウント経由で行い、Emacs・git は descartes/raspi 上で実行する。

## ブランチ構成

- `master`: 共通コード・ドキュメント
- `client`: client/ 以下の開発用
- `server`: server/ 以下の開発用
- `develop`: 現在の開発ブランチ（master・client・server へのマージ前作業）

descartes と raspi 間のコード同期は GitHub 経由で行う（sshfs は遅すぎるため）。

## 開発コマンド

### 環境構築

```bash
# server (Hawking WSL / descartes 共通)
cd server
uv sync --dev
cp dot.env .env  # DATABASE_URL / TOTP_SECRET / SLACK_TOKEN / SLACK_CHANNEL を設定

# client — 開発環境 (Hawking WSL)
cd client
uv sync --dev
cp dot.env .env  # MOCK_SENSORS=1 に設定する

# client — 本番環境 (raspi 実機。lgpio のビルドに実機ライブラリが必要)
cd client
sudo apt install swig python3-dev liblgpio-dev
uv python install 3.13
uv sync --no-dev --extra raspi
cp dot.env .env  # SERVER_URL / TOTP_SECRET を設定する
```

Hawking WSL の MariaDB 起動（WSL 再起動後に必要な場合）:
```bash
sudo service mysql start
```

### server の起動・テスト

```bash
cd server
uv run uvicorn main:app --reload   # 開発サーバー起動（http://127.0.0.1:8000）
uv run pytest                      # テスト実行
uv run python monitor.py           # モニター手動実行
uv run python daily_report.py      # 日次レポート手動実行
```

### client スクリプト実行・テスト

```bash
cd client
uv run python tmprtr_multi.py   # 全センサー読み取り＋POST（MOCK_SENSORS=1 でスタブ動作）
uv run python temp.py           # DS18B20 のみ
uv run python cputemp.py        # CPU 温度のみ
uv run pytest                   # テスト実行
```

## 実装状況

### client/ 完了済み
- `sensors.py` — センサー読み取り抽象化レイヤー（`MOCK_SENSORS=1` でスタブ動作）
- `tmprtr_multi.py` — 全センサー読み取り＋TOTP 認証付き POST 送信
- `tmprtr.crontab` — 1分おき実行の cron 設定（`CRON_TZ=Asia/Tokyo`）
- `temp.py` — DS18B20 温度センサー読み取り (w1thermsensor)
- `cputemp.py` — CPU 温度取得 (gpiozero + lgpio)
- `test_sensors.py` — pytest テスト（モックパス・本番パス両方）
- `test_tmprtr_multi.py` — POST 送信のテスト

### server/ 完了済み
- `main.py` — FastAPI アプリ。`POST /sensor_data`（TOTP 認証）、`GET /graph`（gnuplot PNG）
- `graph.py` — gnuplot グラフ生成（期間・センサー種別をパラメータ指定）
- `monitor.py` — データなし・高温・低温を検知し escalation 付きで Slack 通知
- `daily_report.py` — 最新値・24h サマリー・異常を毎日 8:00 に Slack 送信
- `slack_notify.py` — Slack 送信ヘルパー
- `monitor.crontab` — 毎分実行の cron 設定
- `daily_report.crontab` — 毎日 8:00 実行の cron 設定
- `database.py` — SQLAlchemy Engine / SessionLocal / `get_db()`
- `models.py` — SQLAlchemy モデル（`Tmprtr`、`Sensors`、`Notifications` など）

### 未実装
特になし。

## server/ の構成詳細

### エンドポイント
- `POST /sensor_data` — TOTP 認証付きでセンサーデータを受信・DB 保存
- `GET /graph?hours=24&sensor=all` — gnuplot で PNG グラフ生成。`sensor` は `all`/`cpu`/`other`

### 認証
TOTP（RFC 6238）によるリクエストヘッダー認証。クライアントは `X-TOTP-Code: <pyotp.TOTP(secret).now()>` を付けて送信する。シークレット生成:

```bash
uv run python -c "import pyotp; print(pyotp.random_base32())"
```

### Slack 通知
`SLACK_TOKEN`（Bot Token）と `SLACK_CHANNEL` を `.env` に設定する。  
`notifications` テーブル（id=1: No Data、id=2: 高温、id=3: 低温）と `notification_intervals` テーブルで通知間隔を管理する。

## client/ の構成詳細

- `sensors.py` — `MOCK_SENSORS=1` でスタブ値を返し、本番は `gpiozero` / `w1thermsensor` を遅延 import して読む
- `tmprtr_multi.py` — `sensors.py` で全センサー読み取り後、`SERVER_URL` / `TOTP_SECRET` を使って POST 送信

### センサー読み取りのデータ形式

`sensors.read_all_sensors()` の返却形式:

```python
[{'id': 'cpu', 'temperature': 50.0}, {'id': '<DS18B20シリアルID>', 'temperature': 23.5}, ...]
```
