# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Raspberry Pi の温度センサー監視システム。Ruby CGI で書かれた旧リポジトリ `raspi` を Python で再構成している。

- **client/**: raspi 上で動作。DS18B20 センサーと CPU 温度を読み取り、サーバーへ POST する。
- **server/**: descartes 上で動作。受信データを MySQL に保存し gnuplot でグラフ生成する（実装予定）。

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

descartes と raspi 間のコード同期は GitHub 経由で行う（sshfs は遅すぎるため）。

## 開発コマンド

### 環境構築

```bash
# client (raspi 上)
cd client
uv python install 3.13
uv sync
sudo apt install swig python3-dev liblgpio-dev  # lgpio ビルドに必要

# server (descartes 上)
cd server
uv python install 3.13
uv sync
cp dot.env .env  # .env を編集して DATABASE_URL と TOTP_SECRET を設定
```

### server の起動・テスト

```bash
cd server
uv run uvicorn main:app --reload   # 開発サーバー起動（http://127.0.0.1:8000）
uv run pytest                      # テスト実行

# データ送信テスト（TOTP コードは Python で生成）
# python -c "import pyotp; print(pyotp.TOTP('シークレット').now())"
curl -X POST http://127.0.0.1:8000/sensor_data \
    -H "Content-Type: application/json" \
    -H "X-TOTP-Code: <TOTP コード>" \
    -d '{"sensor_id": "SENSOR01", "temperature": 23.456}'
```

### client スクリプト実行

```bash
cd client
uv run python tmprtr_multi.py   # 全センサー読み取り
uv run python temp.py           # DS18B20 のみ
uv run python cputemp.py        # CPU 温度のみ
```

## 実装状況と今後の作業

### client/ 完了済み
- `temp.py` — DS18B20 温度センサー読み取り (w1thermsensor)
- `cputemp.py` — CPU 温度取得 (gpiozero + lgpio)
- `httpsget.py` — HTTPS GET テスト (requests)
- `tmprtr_multi.py` — 複数センサー統合読み取り

### client/ 未実装
- POST 送信機能 (`tmprtr_multi.py` に追加予定)
  - エンドポイント: `requests.post(url, data={"i": id, "t": temp, "k": key})`
  - server 側の POST エンドポイント完成後に実装
- cron 登録スクリプト (`tmprtr.crontab`)
  - `CRON_TZ=Asia/Tokyo` を設定すること

### server/ 完了済み
- FastAPI による POST 受信エンドポイント `/sensor_data`（TOTP 認証付き）
- SQLAlchemy + MariaDB への書き込み（`tmprtr` テーブル）
- loguru によるログ出力（`logs/sensor_*.log`）

### server/ 未実装
- gnuplot によるグラフ生成

## server/ の構成

- `main.py` — FastAPI アプリ。`POST /sensor_data` エンドポイント、TOTP 認証、loguru ログ
- `database.py` — SQLAlchemy Engine / SessionLocal / `get_db()` ジェネレータ（`.env` から接続情報を読む）
- `models.py` — sqlacodegen で生成した SQLAlchemy モデル（`Tmprtr`、`Sensors`、`Notifications` など）
- `dot.env` — `.env` のテンプレート（`DATABASE_URL`、`TOTP_SECRET`）
- `test_main.py` — pytest テスト（`get_db` と `verify_totp` を `dependency_overrides` でモック）

### 認証

TOTP（RFC 6238）によるリクエストヘッダー認証。クライアントは `X-TOTP-Code: <pyotp.TOTP(secret).now()>` を付けて送信する。シークレット生成:

```bash
uv run python -c "import pyotp; print(pyotp.random_base32())"
```

## データ形式

`tmprtr_multi.py` のセンサー読み取り返却形式:

```python
[{'id': 'cpu', 'temperature': 50.0}, {'id': '<DS18B20シリアルID>', 'temperature': 23.5}, ...]
```
