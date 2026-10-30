"""Import the supplied sample CSV as UNVERIFIED historical records.
Run from the backend folder after the first backend start has created the DB:
    python import_sample_csv.py
"""
import csv, sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CSV_PATH = BASE / "data" / "accidents_sample_cleaned_unverified.csv"
DB_PATH = Path(__file__).resolve().parent / "saferoute.db"
now = datetime.now(timezone.utc).isoformat()
con = sqlite3.connect(str(DB_PATH))
con.execute("""CREATE TABLE IF NOT EXISTS historical_accidents (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lat REAL NOT NULL, lon REAL NOT NULL,
 occurred_at TEXT, year INTEGER, hour INTEGER, area TEXT, district TEXT, state TEXT,
 vehicle TEXT, severity TEXT, source TEXT NOT NULL, source_url TEXT,
 verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
inserted = 0
for r in rows:
    try:
        lat, lon = float(r['latitude']), float(r['longitude'])
        date = datetime.strptime(r['date'], '%Y-%m-%d')
        hour = int(r['hour']) if r['hour'].strip() else None
        if not (6 <= lat <= 38.5 and 68 <= lon <= 98.5):
            continue
        if hour is not None and not 0 <= hour <= 23:
            hour = None
        # Idempotent import: the same sample ID is not inserted twice.
        exists = con.execute("SELECT 1 FROM historical_accidents WHERE source=? AND occurred_at=? AND area=? AND lat=? AND lon=?",
            ('User-supplied sample CSV (UNVERIFIED)', date.isoformat(), r['area'], lat, lon)).fetchone()
        if exists:
            continue
        con.execute("""INSERT INTO historical_accidents
        (lat,lon,occurred_at,year,hour,area,district,state,vehicle,severity,source,source_url,verified,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (lat,lon,date.isoformat(),date.year,hour,r['area'],None,'Tamil Nadu',r['vehicle'],r['severity'],
         'User-supplied sample CSV (UNVERIFIED)',None,0,now))
        inserted += 1
    except (ValueError, KeyError):
        continue
con.commit()
count = con.execute("SELECT COUNT(*) FROM historical_accidents WHERE source='User-supplied sample CSV (UNVERIFIED)'").fetchone()[0]
con.close()
print('Sample import complete.')
print('New records inserted:', inserted)
print('Total sample records in database:', count)
print('IMPORTANT: These records remain UNVERIFIED and must not be presented as official accident history.')
