from flask import Blueprint, jsonify, request
import uuid
import json
from datetime import datetime, UTC

from kyc.db import get_db

session_bp = Blueprint("session", __name__, url_prefix="/session")


@session_bp.route("/start", methods=["POST"])
def start_session():
    session_id = str(uuid.uuid4())
    user_agent = request.headers.get("User-Agent", "unknown")
    ip_address = request.remote_addr

    db = get_db()
    cur = db.cursor()

    now = datetime.now(UTC).isoformat()

    cur.execute("""
        INSERT INTO verification_sessions (
            id, status, current_step, user_agent, ip_address, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, "started", 1, user_agent, ip_address, now, now))

    db.commit()
    db.close()

    return jsonify({"success": True, "session_id": session_id, "status": "started"})


@session_bp.route("/status/<session_id>", methods=["GET"])
def session_status(session_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM verification_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return jsonify({"success": False, "error": "session not found"}), 404

    data = dict(row)

    # convert ints to bools
    for k in ["liveness_running", "liveness_completed", "liveness_verified", "verify_verified"]:
        if k in data and data[k] is not None:
            data[k] = bool(data[k])

    # optional: decode challenges JSON for API
    if data.get("liveness_challenges"):
        try:
            data["liveness_challenges"] = json.loads(data["liveness_challenges"])
        except Exception:
            pass

    return jsonify({"success": True, "session": data})


@session_bp.route("/liveness-result", methods=["POST"])
def liveness_result():
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id"}), 400

    challenges = data.get("challenges") or {}
    challenges_json = json.dumps(challenges, ensure_ascii=False)

    completed_count = sum(1 for v in challenges.values() if v is True)
    total_count = len(challenges) if challenges else 4

    verified = 1 if bool(data.get("verified")) else 0
    confidence = float(data.get("confidence") or 0.0)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM verification_sessions WHERE id = ?", (session_id,))
    if cur.fetchone() is None:
        conn.close()
        return jsonify({"success": False, "error": "Session not found"}), 404

    now = datetime.now(UTC).isoformat()

    cur.execute("""
        UPDATE verification_sessions
        SET
            liveness_running = 0,
            liveness_completed = 1,
            liveness_verified = ?,
            liveness_confidence = ?,
            liveness_challenges = ?,
            liveness_completed_count = ?,
            liveness_total_count = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        verified,
        confidence,
        challenges_json,
        completed_count,
        total_count,
        now,
        session_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "session_id": session_id,
        "liveness_verified": bool(verified),
        "liveness_confidence": confidence,
        "liveness_completed_count": completed_count,
        "liveness_total_count": total_count,
        "liveness_challenges": challenges
    })
