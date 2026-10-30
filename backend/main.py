"""
SafeRoute AI backend (Flask + SQLite)
Public:
  GET /health
  GET /api/accidents/historical
  GET /api/accidents/live

Admin (requires X-Admin-Key):
  POST /api/admin/historical
  POST /api/admin/incidents
  PATCH /api/admin/incidents/<incident_id>
  DELETE /api/admin/incidents/<incident_id>

This backend stores data received from authorised sources/operators.
It does not independently discover every accident in India.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

allowed_origins = os.getenv("SAFEROUTE_ALLOWED_ORIGINS", "*")
CORS(app, origins=[x.strip() for x in allowed_origins.split(",") if x.strip()])

DB_PATH = os.getenv("SAFEROUTE_DB", "saferoute.db")
ADMIN_API_KEY = os.getenv("SAFEROUTE_ADMIN_KEY", "")
LIVE_WINDOW_HOURS = int(os.getenv("SAFEROUTE_LIVE_WINDOW_HOURS", "24"))


def now_utc():
    return datetime.now(timezone.utc)


def iso_now():
    return now_utc().isoformat()


def parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise ValueError("Datetime must be ISO-8601, e.g. 2026-10-30T10:30:00Z")


def india_coordinates(lat, lon):
    return 6.0 <= lat <= 38.5 and 68.0 <= lon <= 98.5


def connect_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect_db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS historical_accidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL, lon REAL NOT NULL, occurred_at TEXT,
            year INTEGER, hour INTEGER, area TEXT, district TEXT, state TEXT,
            vehicle TEXT, severity TEXT, source TEXT NOT NULL, source_url TEXT,
            verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS citizen_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL, lon REAL NOT NULL, title TEXT NOT NULL,
            description TEXT, incident_type TEXT NOT NULL,
            reported_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review',
            created_at TEXT NOT NULL
        )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_reports_status_time ON citizen_reports(status, reported_at)")
        con.execute("""
        CREATE TABLE IF NOT EXISTS live_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL, lon REAL NOT NULL, title TEXT NOT NULL,
            incident_type TEXT, status TEXT NOT NULL DEFAULT 'reported',
            reported_at TEXT NOT NULL, source TEXT NOT NULL, source_url TEXT,
            verified INTEGER NOT NULL DEFAULT 0, expires_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_hist_year ON historical_accidents(year)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_live_status_time ON live_incidents(status, reported_at)")
        con.commit()


def admin_required():
    if not ADMIN_API_KEY:
        return jsonify({
            "error": "Admin writes are disabled. Set SAFEROUTE_ADMIN_KEY on the server."
        }), 503
    if request.headers.get("X-Admin-Key") != ADMIN_API_KEY:
        return jsonify({"error": "Valid X-Admin-Key header required."}), 401
    return None


def make_feature_collection(rows, is_live=False):
    features = []
    for row in rows:
        p = dict(row)
        lat, lon = p.pop("lat"), p.pop("lon")
        p.pop("id", None)
        p["verified"] = bool(p.get("verified", 0))
        p["verification"] = "verified" if p["verified"] else "unverified"
        if is_live:
            p["reportedAt"] = p.pop("reported_at", None)
            p["title"] = p.get("title") or "Reported road incident"
            p["status"] = p.get("status") or "reported"
            p["source"] = p.get("source") or "Not supplied"
        else:
            p["hour"] = p.get("hour") if p.get("hour") is not None else -1
            p["area"] = p.get("area") or p.get("district") or p.get("state") or "Recorded location"
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": p
        })
    return {"type": "FeatureCollection", "features": features}


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "name": "SafeRoute AI API",
        "health": "/health",
        "historical": "/api/accidents/historical",
        "live": "/api/accidents/live",
        "note": "Live coverage depends on authorised feeds connected to this server."
    })


@app.route("/health", methods=["GET"])
def health():
    with connect_db() as con:
        historical = con.execute("SELECT COUNT(*) FROM historical_accidents").fetchone()[0]
        live = con.execute(
            "SELECT COUNT(*) FROM live_incidents WHERE status IN ('reported','verified')"
        ).fetchone()[0]
    return jsonify({
        "status": "ok",
        "time": iso_now(),
        "historical_records": historical,
        "open_live_incidents": live
    })


@app.route("/api/accidents/historical", methods=["GET"])
def get_historical():
    state = request.args.get("state")
    year_from = request.args.get("year_from", type=int)
    year_to = request.args.get("year_to", type=int)
    limit = min(max(request.args.get("limit", 5000, type=int), 1), 20000)

    sql = "SELECT * FROM historical_accidents WHERE 1=1"
    args = []
    if state:
        sql += " AND lower(state)=lower(?)"
        args.append(state)
    if year_from is not None:
        sql += " AND year >= ?"
        args.append(year_from)
    if year_to is not None:
        sql += " AND year <= ?"
        args.append(year_to)
    sql += " ORDER BY year DESC LIMIT ?"
    args.append(limit)

    with connect_db() as con:
        rows = con.execute(sql, args).fetchall()
    return jsonify(make_feature_collection(rows, False))


@app.route("/api/accidents/live", methods=["GET"])
def get_live():
    cutoff = (now_utc() - timedelta(hours=LIVE_WINDOW_HOURS)).isoformat()
    current = iso_now()
    with connect_db() as con:
        rows = con.execute("""
            SELECT * FROM live_incidents
            WHERE status IN ('reported','verified')
              AND reported_at >= ?
              AND (expires_at IS NULL OR expires_at >= ?)
            ORDER BY reported_at DESC LIMIT 5000
        """, (cutoff, current)).fetchall()
    return jsonify(make_feature_collection(rows, True))


@app.route("/api/reports", methods=["POST"])
def submit_citizen_report():
    """Accept a citizen report into a private moderation queue; never publish it directly."""
    body = request.get_json(silent=True) or {}
    try:
        lat = float(body["latitude"])
        lon = float(body["longitude"])
        title = str(body.get("title", "")).strip()
        description = str(body.get("description", "")).strip()[:1000]
        incident_type = str(body.get("incident_type", "road_hazard")).strip()
        if not india_coordinates(lat, lon):
            raise ValueError("Coordinates are outside the supported India area.")
        if len(title) < 4 or len(title) > 120:
            raise ValueError("Title must be between 4 and 120 characters.")
        if incident_type not in ("accident", "road_hazard", "traffic_block", "vehicle_breakdown", "other"):
            raise ValueError("Unsupported incident type.")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 422

    with connect_db() as con:
        cur = con.execute("""
            INSERT INTO citizen_reports
            (lat,lon,title,description,incident_type,reported_at,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (lat, lon, title, description, incident_type, iso_now(), "pending_review", iso_now()))
        con.commit()
        report_id = cur.lastrowid
    return jsonify({
        "accepted": True,
        "report_id": report_id,
        "status": "pending_review",
        "message": "Report received. It will not appear on the public map until reviewed."
    }), 201


@app.route("/api/admin/reports", methods=["GET"])
def list_citizen_reports():
    denied = admin_required()
    if denied:
        return denied
    with connect_db() as con:
        rows = con.execute("""
            SELECT id,lat,lon,title,description,incident_type,reported_at,status
            FROM citizen_reports WHERE status='pending_review' ORDER BY reported_at DESC LIMIT 500
        """).fetchall()
    return jsonify({"reports": [dict(row) for row in rows]})


@app.route("/api/admin/reports/<int:report_id>/approve", methods=["POST"])
def approve_citizen_report(report_id):
    """Moderator confirms a report and publishes it as a reviewed live incident."""
    denied = admin_required()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    source = str(body.get("source", "Moderator-reviewed citizen report")).strip()
    if len(source) < 3:
        return jsonify({"error": "A source/review note is required."}), 422
    with connect_db() as con:
        row = con.execute("SELECT * FROM citizen_reports WHERE id=? AND status='pending_review'", (report_id,)).fetchone()
        if not row:
            return jsonify({"error": "Pending report not found."}), 404
        expiry = now_utc() + timedelta(hours=24)
        cur = con.execute("""
            INSERT INTO live_incidents
            (lat,lon,title,incident_type,status,reported_at,source,source_url,
             verified,expires_at,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            row["lat"], row["lon"], row["title"], row["incident_type"], "verified",
            row["reported_at"], source, None, 1, expiry.isoformat(), iso_now(), iso_now()
        ))
        con.execute("UPDATE citizen_reports SET status='approved' WHERE id=?", (report_id,))
        con.commit()
        incident_id = cur.lastrowid
    return jsonify({"approved": True, "report_id": report_id, "incident_id": incident_id}), 201


@app.route("/api/admin/reports/<int:report_id>/reject", methods=["POST"])
def reject_citizen_report(report_id):
    denied = admin_required()
    if denied:
        return denied
    with connect_db() as con:
        cur = con.execute("UPDATE citizen_reports SET status='rejected' WHERE id=? AND status='pending_review'", (report_id,))
        con.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Pending report not found."}), 404
    return jsonify({"rejected": True, "report_id": report_id})


@app.route("/api/admin/historical", methods=["POST"])
def add_historical():
    denied = admin_required()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    records = body.get("records")
    if not isinstance(records, list) or not records or len(records) > 5000:
        return jsonify({"error": "Send records as a non-empty array (maximum 5000)."}), 400

    accepted = 0
    skipped = 0
    try:
        with connect_db() as con:
            for item in records:
                lat = float(item["latitude"])
                lon = float(item["longitude"])
                if not india_coordinates(lat, lon):
                    skipped += 1
                    continue
                occurred = parse_time(item.get("occurred_at"))
                year = item.get("year") or (occurred.year if occurred else None)
                hour = item.get("hour")
                if hour is None and occurred:
                    hour = occurred.hour
                if hour is not None:
                    hour = int(hour)
                    if hour < 0 or hour > 23:
                        raise ValueError("hour must be between 0 and 23")
                source = str(item.get("source", "")).strip()
                if len(source) < 2:
                    raise ValueError("Every historical record needs a source name.")
                con.execute("""
                    INSERT INTO historical_accidents
                    (lat,lon,occurred_at,year,hour,area,district,state,vehicle,severity,
                     source,source_url,verified,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    lat, lon, occurred.isoformat() if occurred else None, year, hour,
                    item.get("area"), item.get("district"), item.get("state"),
                    item.get("vehicle", "Unknown"), item.get("severity", "Unknown"),
                    source, item.get("source_url"), int(bool(item.get("verified", False))),
                    iso_now()
                ))
                accepted += 1
            con.commit()
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify({
        "accepted": accepted,
        "submitted": len(records),
        "skipped_outside_india": skipped
    })


@app.route("/api/admin/incidents", methods=["POST"])
def add_live_incident():
    denied = admin_required()
    if denied:
        return denied
    item = request.get_json(silent=True) or {}
    try:
        lat = float(item["latitude"])
        lon = float(item["longitude"])
        title = str(item["title"]).strip()
        source = str(item["source"]).strip()
        if not india_coordinates(lat, lon):
            raise ValueError("Coordinates are outside the supported India bounding area.")
        if len(title) < 3 or len(source) < 2:
            raise ValueError("title and source are required.")
        status = item.get("status", "reported")
        if status not in ("reported", "verified", "resolved"):
            raise ValueError("status must be reported, verified, or resolved.")
        reported = parse_time(item.get("reported_at")) or now_utc()
        expiry_hours = int(item.get("expires_in_hours", 24))
        if expiry_hours < 1 or expiry_hours > 168:
            raise ValueError("expires_in_hours must be from 1 to 168.")
        expires = reported + timedelta(hours=expiry_hours)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 422

    with connect_db() as con:
        cur = con.execute("""
            INSERT INTO live_incidents
            (lat,lon,title,incident_type,status,reported_at,source,source_url,
             verified,expires_at,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            lat, lon, title, item.get("incident_type", "road_accident"), status,
            reported.isoformat(), source, item.get("source_url"),
            int(bool(item.get("verified", False))), expires.isoformat(), iso_now(), iso_now()
        ))
        con.commit()
        incident_id = cur.lastrowid

    return jsonify({
        "id": incident_id,
        "accepted": True,
        "status": status,
        "expires_at": expires.isoformat()
    }), 201


@app.route("/api/admin/incidents/<int:incident_id>", methods=["PATCH"])
def update_live_incident(incident_id):
    denied = admin_required()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in ("reported", "verified", "resolved"):
        return jsonify({"error": "status must be reported, verified, or resolved."}), 422

    with connect_db() as con:
        found = con.execute("SELECT id FROM live_incidents WHERE id=?", (incident_id,)).fetchone()
        if not found:
            return jsonify({"error": "Incident not found."}), 404
        if "verified" in body:
            con.execute(
                "UPDATE live_incidents SET status=?, verified=?, updated_at=? WHERE id=?",
                (status, int(bool(body["verified"])), iso_now(), incident_id)
            )
        else:
            con.execute(
                "UPDATE live_incidents SET status=?, updated_at=? WHERE id=?",
                (status, iso_now(), incident_id)
            )
        con.commit()
    return jsonify({"id": incident_id, "status": status, "updated": True})


@app.route("/api/admin/incidents/<int:incident_id>", methods=["DELETE"])
def delete_live_incident(incident_id):
    denied = admin_required()
    if denied:
        return denied
    with connect_db() as con:
        cur = con.execute("DELETE FROM live_incidents WHERE id=?", (incident_id,))
        con.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Incident not found."}), 404
    return jsonify({"id": incident_id, "deleted": True})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
