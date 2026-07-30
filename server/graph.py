"""gnuplot によるグラフ生成モジュール。"""
import subprocess
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import quantiles
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import Sensors

# サーバー（MariaDB）の UTC オフセット（時、東方向が正）
_server_tz_hours = -time.timezone / 3600

# グラフ 1 本あたりの最大描画点数（SQL 集計で制限）
_MAX_POINTS = 2000

# DB クエリのタイムアウト秒数（MariaDB max_statement_time）
_QUERY_TIMEOUT_SECS = 30


def generate_graph(
    db: Session,
    hours: int,
    sensor: str,
    tz_offset: int = 0,
    start: Optional[datetime] = None,
) -> bytes:
    """指定期間・センサー種別のグラフを PNG バイト列で返す。"""
    if start is not None:
        since = start
        until = start + timedelta(hours=hours)
    else:
        until = datetime.now()
        since = until - timedelta(hours=hours)
    # DB はサーバー TZ で記録されているため、表示ずれを補正してブラウザ TZ に変換する
    tz_delta = timedelta(hours=tz_offset - _server_tz_hours)

    sensor_names = {s.sensor_id: s.print_name or s.sensor_id for s in db.query(Sensors).all()}

    total_secs = int((until - since).total_seconds())
    bucket_secs = max(60, total_secs // _MAX_POINTS)

    # ホスト名付き CPU センサー ID（例: raspi2_cpu）も CPU として扱う（collation は
    # utf8mb4_general_ci で大小文字を区別しないため '%_CPU' で '%_cpu' にも一致する）
    _is_cpu = "(sensor_id = 'cpu' OR sensor_id LIKE '%_CPU')"
    sensor_conditions = {
        "cpu": _is_cpu,
        "other": f"NOT {_is_cpu}",
        "indoor": f"NOT {_is_cpu} AND sensor_id != 'EstimatedOutdoor'",
        "all": "TRUE",
    }
    sensor_cond = sensor_conditions.get(sensor, "TRUE")

    # DB クエリタイムアウトをセッション単位で設定し、SQL レベルで集計・間引きして取得する
    db.execute(text(f"SET max_statement_time={_QUERY_TIMEOUT_SECS}"))
    sql = text(
        f"SELECT sensor_id,"
        f" FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(event_datetime) / :bucket) * :bucket) AS dt,"
        f" AVG(tmprtr) AS tmprtr"
        f" FROM tmprtr"
        f" WHERE event_datetime BETWEEN :since AND :until AND {sensor_cond}"
        f" GROUP BY sensor_id, FLOOR(UNIX_TIMESTAMP(event_datetime) / :bucket)"
        f" ORDER BY sensor_id, dt"
    )
    rows = db.execute(sql, {"bucket": bucket_secs, "since": since, "until": until}).fetchall()

    if not rows:
        raise ValueError("指定期間にデータがありません")

    by_sensor = defaultdict(list)
    for row in rows:
        by_sensor[row.sensor_id].append(row)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_files = {}
        yrange_lo_list = []
        yrange_hi_list = []
        for sid, recs in by_sensor.items():
            temps = [float(r.tmprtr) for r in recs]
            if len(temps) >= 4:
                q1, q3 = quantiles(temps, n=4)[0], quantiles(temps, n=4)[2]
                iqr = q3 - q1
                yrange_lo_list.append(q1 - 1.5 * iqr)
                yrange_hi_list.append(q3 + 1.5 * iqr)
            path = f"{tmpdir}/{sid}.dat"
            with open(path, "w") as f:
                for r in recs:
                    dt = (r.dt + tz_delta).strftime('%Y-%m-%dT%H:%M:%S')
                    f.write(f"{dt} {float(r.tmprtr)}\n")
            data_files[sid] = path

        plot_parts = []
        for sid, path in data_files.items():
            name = sensor_names.get(sid, sid)
            plot_parts.append(f'"{path}" using 1:2 with linespoints title "{name}" noenhanced')

        duration_hours = (until - since).total_seconds() / 3600
        xfmt = "%m/%d\\n%H:%M" if duration_hours <= 7 * 24 else "%Y/%m/%d"
        yrange_line = (
            f"set yrange [{min(yrange_lo_list):.1f}:{max(yrange_hi_list):.1f}]\n"
            if yrange_lo_list else ""
        )
        script = (
            "set terminal png size 1200,600\n"
            f'set output "{tmpdir}/graph.png"\n'
            "set xdata time\n"
            'set timefmt "%Y-%m-%dT%H:%M:%S"\n'
            f'set format x "{xfmt}"\n'
            "set ylabel \"Temperature (C)\"\n"
            "set grid\n"
            "set key outside right\n"
            f"{yrange_line}"
            f"plot {', '.join(plot_parts)}\n"
        )

        script_path = f"{tmpdir}/plot.gp"
        with open(script_path, "w") as f:
            f.write(script)

        subprocess.run(["gnuplot", script_path], check=True, capture_output=True, timeout=60)

        with open(f"{tmpdir}/graph.png", "rb") as f:
            return f.read()
