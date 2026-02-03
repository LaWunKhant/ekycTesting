from flask import Blueprint, jsonify, request
import uuid
from datetime import datetime, timezone

from kyc.db import get_db

session_bp = Blueprint('session', __name__, url_prefix='/session')


@session_bp.route('/start', methods=['POST'])
def start_session():
    """
    Start a new KYC session
    """
    session_id = str(uuid.uuid4())
    user_agent = request.headers.get('User-Agent', 'unknown')
    ip_address = request.remote_addr

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO verification_sessions (
            id,
            status,
            current_step,
            user_agent,
            ip_address,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        "started",
        1,
        user_agent,
        ip_address,
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat()
    ))

    db.commit()

    return jsonify({
        "success": True,
        "session_id": session_id,
        "status": "started"
    })


@session_bp.route('/status/<session_id>', methods=['GET'])
def session_status(session_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM verification_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return jsonify({"success": False, "error": "session not found"}), 404

    # sqlite3.Row -> dict
    data = dict(row)

    # (optional) convert int flags to real booleans for API consumers
    for k in ["liveness_running", "liveness_completed", "liveness_verified", "verify_verified"]:
        if k in data and data[k] is not None:
            data[k] = bool(data[k])

    return jsonify({"success": True, "session": data})

@session_bp.route("/liveness-result", methods=["POST"])
def save_liveness_result():
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id"}), 400

    # accept either naming style
    verified = bool(data.get("verified", False))
    confidence = float(data.get("confidence", 0.0))

    # optional flags
    running = bool(data.get("running", False))
    completed = bool(data.get("completed", True))  # result usually means completed

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM verification_sessions WHERE id = ?", (session_id,))
    if cur.fetchone() is None:
        conn.close()
        return jsonify({"success": False, "error": "Session not found"}), 404

    cur.execute("""
        UPDATE verification_sessions
        SET
            liveness_running = ?,
            liveness_completed = ?,
            liveness_verified = ?,
            liveness_confidence = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        1 if running else 0,
        1 if completed else 0,
        1 if verified else 0,
        confidence,
        datetime.now(timezone.utc).isoformat(),
        session_id
    ))

    conn.commit()
    conn.close()

    return jsonify({"success": True})
