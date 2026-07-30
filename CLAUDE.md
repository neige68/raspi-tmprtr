# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 開発環境

- **作業場所**: 開発マシン上のローカルクローン
- **server の本番環境**: Linux サーバー（`~/raspi-tmprtr/`）
- **client の本番環境**: Raspberry Pi（`~/raspi-tmprtr/`）

開発・テストはローカルクローンで完結させ、動作確認後に push する。  
client は `MOCK_SENSORS=1` でスタブ動作するため、実機なしでもテスト可能。  
実センサー（gpiozero / w1thermsensor）の動作確認は Raspberry Pi 実機でのみ可能。

## プロジェクト概要

Raspberry Pi の温度センサー監視システム。

- **client/**: Raspberry Pi 上で動作。DS18B20 センサーと CPU 温度を読み取り、サーバーへ POST する。
- **server/**: Linux サーバー上で動作。受信データを MariaDB に保存し、グラフ生成・異常監視・Slack 通知を行う。

## ブランチ構成

- `master`: 共通コード・ドキュメント
- `client`: client/ 以下の開発用
- `server`: server/ 以下の開発用
- `develop`: 現在の開発ブランチ（master・client・server へのマージ前作業）

## 開発コマンド

### 環境構築

```bash
# server
cd server
uv sync --dev
cp dot.env .env  # DATABASE_URL / TOTP_SECRET / SLACK_TOKEN / SLACK_CHANNEL を設定

# client — 開発環境
cd client
uv sync --dev
cp dot.env .env  # MOCK_SENSORS=1 に設定する

# client — 本番環境 (Raspberry Pi 実機。lgpio のビルドに実機ライブラリが必要)
cd client
sudo apt install swig python3-dev liblgpio-dev
uv python install 3.13
uv sync --no-dev --extra raspi
cp dot.env .env  # SERVER_URL / TOTP_SECRET を設定する
```

開発環境で MariaDB を手動起動する場合（再起動後など）:
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
- `main.py` — FastAPI アプリ。`POST /sensor_data`（TOTP 認証）、`GET /graph`（gnuplot PNG）、`GET /graph/view`（自動リフレッシュ HTML）
- `graph.py` — gnuplot グラフ生成（期間・センサー種別・タイムゾーンオフセットをパラメータ指定）。SQL の時間バケット集計（`GROUP BY FLOOR(UNIX_TIMESTAMP / bucket_secs)`）でセンサー 1 本あたり最大 2000 点に間引いてから取得する。MariaDB の `max_statement_time=30` でクエリタイムアウトも設定済み
- `monitor.py` — データなし・高温・低温を検知し escalation 付きで Slack 通知。高温・低温通知には違反時の温度を付加（例: `High Temp (35.2°C): 5 minutes`）
- `daily_report.py` — 最新値・24h サマリー・異常を毎日 8:00 に Slack 送信
- `slack_notify.py` — Slack 送信ヘルパー
- `monitor.crontab` — 毎分実行の cron 設定
- `daily_report.crontab` — 毎日 8:00 実行の cron 設定
- `outdoor_temp.py` — OpenWeatherMap から推定屋外気温を取得し sensor_id=`EstimatedOutdoor` で DB 保存
- `outdoor_temp.crontab` — 5 分ごと実行の cron 設定
- `database.py` — SQLAlchemy Engine / SessionLocal / `get_db()`
- `models.py` — SQLAlchemy モデル（`Tmprtr`、`Sensors`、`Notifications` など）

### 未実装
特になし。

## server/ の構成詳細

### エンドポイント
- `GET /` — グラフページへのリンク一覧 HTML（6h/all、6h/all（外れ値除去なし）、24h/other、168h/other）
- `POST /sensor_data` — TOTP 認証付きでセンサーデータを受信・DB 保存
- `GET /graph?hours=24&sensor=all&tz=9[&start=ISO8601][&show_outliers=true]` — gnuplot で PNG グラフ生成。センサーごとに IQR 法（Q1−1.5×IQR ～ Q3+1.5×IQR）で外れ値を Y 軸レンジから除外（`show_outliers=true` で無効化し全データを表示）。`sensor` は `all`/`cpu`/`other`/`indoor`、`tz` はタイムゾーンオフセット（時）、`start` は開始日時（省略時は `now - hours`〜`now`、指定時は `start`〜`start + hours`）。DB クエリは SQL で時間バケット集計（最大 2000 点）してから取得するため、長期間指定でも応答時間は一定
- `GET /graph/view?hours=24&sensor=all&tz=9[&start=ISO8601][&show_outliers=true]` — グラフを 1 分自動リフレッシュする HTML ページ

### graph.py の設計上の注意

長期間グラフ（数ヶ月分）でサーバーが応答不能になる問題を経験済み。以下の設計を維持すること:

- **ダウンサンプリングは必ず SQL レベルで行う** — Python で `query.all()` してから間引くと、数十万行が一度メモリ・ネットワークに流れてボトルネックになる
- SQL: `GROUP BY FLOOR(UNIX_TIMESTAMP(event_datetime) / :bucket)` で時間バケット集計
- `bucket_secs = max(60, total_secs // 2000)` — 期間に応じて自動調整
- `SET max_statement_time=30` — クエリを 30 秒でタイムアウトさせる（`OperationalError` を捕捉して 504 を返す）
- `subprocess.run(..., timeout=60)` — gnuplot プロセスのタイムアウト

gnuplot の凡例（`title`）にセンサーの `print_name` を使う際の注意:

- **gnuplot はデフォルト（enhanced text）で `_` を下付き文字、`^` を上付き文字として解釈する** — `print_name` にアンダースコアを含むセンサー（例: `raspi2_cpu`）があると凡例表示が崩れる
- 対策: `title "<name>" noenhanced` のように **`title` の直後に `noenhanced` を置く**（`with linespoints` より後に書いても解釈される）
- gnuplot は WSL2 開発環境には未インストールのことがある。導入: `sudo apt-get install -y gnuplot-nox`（X11 不要、PNG 出力のみなのでこれで十分）。バージョン確認: `gnuplot --version`

CPU センサーの判定（`sensor=cpu`/`other`/`indoor` の絞り込み）:

- client 側は CPU センサー ID を `cpu`（従来機）または `<hostname>_cpu`（ホスト名で区別、`client/sensors.py` の `cpu_sensor_id()` 参照）として送ってくる
- そのため SQL の CPU 判定は `sensor_id = 'cpu'` 単独ではなく `(sensor_id = 'cpu' OR sensor_id LIKE '%_CPU')` を使うこと（`sensor_id` の collation は `utf8mb4_general_ci` で大小文字を区別しないため `%_CPU` で `%_cpu` にも一致する）
- `other` / `indoor` はこの CPU 判定を `NOT (...)` で使い、判定ロジックを重複させない

### DB スキーマ変更時の注意

`init_db.py` は `Base.metadata.create_all(bind=engine)` でテーブルを作成するが、**これは新規テーブル作成のみで既存テーブルへの列追加（ALTER TABLE）は行わない**。
`models.py` にカラムを追加したら、開発 DB・本番 DB それぞれで手動 `ALTER TABLE` を実行すること（マイグレーションツールは導入していない）。

```sql
ALTER TABLE <table> ADD COLUMN <col> <type> [NOT NULL DEFAULT ...] AFTER <既存列>;
```

コードを本番へ反映したら **`sudo systemctl restart raspi-tmprtr` が必須**（`git pull` だけでは実行中プロセスに反映されない。詳細は [server/README.md](server/README.md) 参照）。

### 認証
TOTP（RFC 6238）によるリクエストヘッダー認証。クライアントは `X-TOTP-Code: <pyotp.TOTP(secret).now()>` を付けて送信する。シークレット生成:

```bash
uv run python -c "import pyotp; print(pyotp.random_base32())"
```

### Slack 通知
`SLACK_TOKEN`（Bot Token）と `SLACK_CHANNEL` を `.env` に設定する。  
`notifications` テーブル（id=1: No Data、id=2: 高温、id=3: 低温）と `notification_intervals` テーブルで通知間隔を管理する。  
`notifications.value` には直近の違反温度が保存され、高温・低温通知メッセージに反映される。

## client/ の構成詳細

- `sensors.py` — `MOCK_SENSORS=1` でスタブ値を返し、本番は `gpiozero` / `w1thermsensor` を遅延 import して読む
  - `cpu_sensor_id()` — CPU センサーの sensor_id を返す。従来機（hostname=`raspberrypi`）は `cpu`、それ以外は `<hostname>_cpu`（複数台運用時にホスト名で区別するため）。server 側の `sensor=cpu` グラフ絞り込みはこの両方の形式にマッチさせる必要がある（`server/graph.py` 参照）
- `tmprtr_multi.py` — `sensors.py` で全センサー読み取り後、`SERVER_URL` / `TOTP_SECRET` を使って POST 送信

### センサー読み取りのデータ形式

`sensors.read_all_sensors()` の返却形式:

```python
[{'id': 'cpu', 'temperature': 50.0}, {'id': '<DS18B20シリアルID>', 'temperature': 23.5}, ...]
```
