from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "gtfs").is_dir() else HERE / "france"
DB = str(HERE / "france.duckdb")

if not (ROOT / "gtfs").is_dir():
    raise SystemExit(f"gtfs klasörü bulunamadı: {ROOT / 'gtfs'}")
GTFS_FILES = ["agency", "stops", "routes", "trips", "stop_times", "calendar", "calendar_dates", "shapes"]

con = duckdb.connect(DB)
con.execute("INSTALL spatial; LOAD spatial;")


def load_anfr():
    for path in sorted((ROOT / "anfr").rglob("*.txt")):
        table = "anfr_" + path.stem.lower()
        for enc in ("utf-8", "latin-1"):
            try:
                con.execute(
                    f"CREATE OR REPLACE TABLE {table} AS "
                    f"SELECT * FROM read_csv('{path.as_posix()}', delim=';', header=true, all_varchar=true, encoding='{enc}')"
                )
                print(f"{table:35s} {enc}")
                break
            except duckdb.Error as e:
                last = e
        else:
            print(f"{table:35s} HATA -> {last}")


def load_gtfs():
    for name in GTFS_FILES:
        paths = sorted((ROOT / "gtfs").glob(f"*/{name}.txt"))
        if not paths:
            continue
        files = ", ".join(f"'{p.as_posix()}'" for p in paths)
        con.execute(
            f"CREATE OR REPLACE TABLE gtfs_{name} AS "
            f"SELECT split_part(replace(filename, '\\', '/'), '/', -2) AS city, * EXCLUDE (filename) "
            f"FROM read_csv([{files}], union_by_name=true, all_varchar=true, filename=true)"
        )
        print(f"gtfs_{name:30s} {len(paths)} şehir")


def build_views():
    if not con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='gtfs_stops'").fetchone()[0]:
        print(f"\nstops.txt bulunamadı. Şehir klasörlerini kontrol et: {ROOT / 'gtfs'}")
        for d in sorted((ROOT / "gtfs").iterdir()):
            if d.is_dir():
                print(f"  {d.name}: {sorted(p.name for p in d.iterdir())[:8]}")
        return
    con.execute("""
        CREATE OR REPLACE VIEW v_stops AS
        SELECT city, stop_id, stop_name,
               TRY_CAST(stop_lat AS DOUBLE) AS lat,
               TRY_CAST(stop_lon AS DOUBLE) AS lon,
               ST_Point(TRY_CAST(stop_lon AS DOUBLE), TRY_CAST(stop_lat AS DOUBLE)) AS geom
        FROM gtfs_stops
        WHERE TRY_CAST(stop_lat AS DOUBLE) IS NOT NULL
    """)


def report():
    print("\nTablolar:")
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables ORDER BY 1").fetchall():
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:35s} {n:>12,}")
    if con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='gtfs_stops'").fetchone()[0]:
        print("\nŞehir başına durak:")
        for city, n in con.execute("SELECT city, COUNT(*) FROM gtfs_stops GROUP BY 1 ORDER BY 2 DESC").fetchall():
            print(f"  {city:15s} {n:>8,}")


if __name__ == "__main__":
    load_anfr()
    load_gtfs()
    build_views()
    report()
    con.close()
