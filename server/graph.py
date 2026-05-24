"""gnuplot によるグラフ生成モジュール。"""
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import Sensors, Tmprtr


def generate_graph(db: Session, hours: int, sensor: str, tz_offset: int = 9) -> bytes:
    """指定期間・センサー種別のグラフを PNG バイト列で返す。"""
    since = datetime.now() - timedelta(hours=hours)
    tz_delta = timedelta(hours=tz_offset)

    sensor_names = {s.sensor_id: s.print_name or s.sensor_id for s in db.query(Sensors).all()}

    query = db.query(Tmprtr).filter(Tmprtr.event_datetime >= since)
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
        for sid, recs in by_sensor.items():
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

        xfmt = "%m/%d\\n%H:%M" if hours <= 7 * 24 else "%Y/%m/%d"
        script = (
            "set terminal png size 1200,600\n"
            f'set output "{tmpdir}/graph.png"\n'
            "set xdata time\n"
            'set timefmt "%Y-%m-%dT%H:%M:%S"\n'
            f'set format x "{xfmt}"\n'
            "set ylabel \"Temperature (C)\"\n"
            "set grid\n"
            "set key outside right\n"
            f"plot {', '.join(plot_parts)}\n"
        )

        script_path = f"{tmpdir}/plot.gp"
        with open(script_path, "w") as f:
            f.write(script)

        subprocess.run(["gnuplot", script_path], check=True, capture_output=True)

        with open(f"{tmpdir}/graph.png", "rb") as f:
            return f.read()
