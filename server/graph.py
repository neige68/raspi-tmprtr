"""gnuplot によるグラフ生成モジュール。"""
import subprocess
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import quantiles
from typing import Optional

from sqlalchemy.orm import Session

from models import Sensors, Tmprtr

# サーバー（MariaDB）の UTC オフセット（時、東方向が正）
_server_tz_hours = -time.timezone / 3600


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

    query = db.query(Tmprtr).filter(
        Tmprtr.event_datetime >= since,
        Tmprtr.event_datetime <= until,
    )
    if sensor == "cpu":
        query = query.filter(Tmprtr.sensor_id == "cpu")
    elif sensor == "other":
        query = query.filter(Tmprtr.sensor_id != "cpu")
    rows = query.order_by(Tmprtr.sensor_id, Tmprtr.event_datetime).all()

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
                    dt = (r.event_datetime + tz_delta).strftime('%Y-%m-%dT%H:%M:%S')
                    f.write(f"{dt} {float(r.tmprtr)}\n")
            data_files[sid] = path

        plot_parts = []
        for sid, path in data_files.items():
            name = sensor_names.get(sid, sid)
            plot_parts.append(f'"{path}" using 1:2 with linespoints title "{name}"')

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

        subprocess.run(["gnuplot", script_path], check=True, capture_output=True)

        with open(f"{tmpdir}/graph.png", "rb") as f:
            return f.read()
