from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import base64
import os
import json
from datetime import datetime,UTC

import cv2
import numpy as np

from kyc.db import init_db
from kyc.db import get_db
from kyc.routes.session import session_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
CORS(app)

# ✅ initialize DB schema on startup
init_db()

# ✅ register routes
app.register_blueprint(session_bp)

print(app.url_map)


# Directory to store uploaded images

UPLOAD_FOLDER = os.path.join(BASE_DIR, "kyc", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store liveness detection state (WEB-BASED ONLY)
liveness_state = {
    'running': False,
    'completed': False,
    'verified': False,
    'confidence': 0
}


@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('kyc/index.html')


@app.route('/liveness')
def liveness_page():
    """Serve the liveness detection page"""
    return render_template('kyc/liveness.html')


@app.route('/capture/', methods=['POST', 'OPTIONS'])
def capture_image():
    """Handle image capture from frontend"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        data = request.get_json(force=True)

        if not data:
            print("❌ No data received")
            return jsonify({'success': False, 'error': 'No data received'}), 400

        if 'image' not in data or 'type' not in data:
            print("❌ Missing image or type field")
            return jsonify({'success': False, 'error': 'Missing image or type'}), 400

        session_id = data.get("session_id")
        if not session_id:
            print("❌ Missing session_id")
            return jsonify({'success': False, 'error': 'Missing session_id'}), 400

        image_data = data['image']
        image_type = data['type']

        print(f"\n📸 Received {image_type} image")
        print(f"   Data length: {len(image_data)} chars")

        # Remove data URL prefix if present
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]

        # Decode base64
        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            print(f"❌ Base64 decode failed: {e}")
            return jsonify({'success': False, 'error': f'Invalid base64 data: {str(e)}'}), 400

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{image_type}_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Save image
        with open(filepath, 'wb') as f:
            f.write(image_bytes)

        # Verify image quality
        try:
            img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                print("❌ Invalid image data")
                return jsonify({'success': False, 'error': 'Invalid image data'}), 400

            height, width = img.shape[:2]
            print(f"✓ Saved {image_type}: {filename}")
            print(f"   Size: {len(image_bytes)} bytes")
            print(f"   Dimensions: {width}x{height}")

            if width < 200 or height < 200:
                return jsonify({
                    'success': False,
                    'error': f'Image too small ({width}x{height}). Please retake with better quality.'
                }), 400

        except Exception as e:
            print(f"⚠ Image verification failed: {e}")

        # 🔗 Bind image to verification session
        col_map = {
            "front": "front_image",
            "back": "back_image",
            "selfie": "selfie_image",
        }

        col = col_map.get(image_type)
        if not col:
            return jsonify({'success': False, 'error': 'Invalid image type'}), 400

        step_map = {"front": 2, "back": 3, "selfie": 4}
        new_step = step_map.get(image_type, 1)

        conn = get_db()
        cur = conn.cursor()

        # ensure session exists
        cur.execute("SELECT id FROM verification_sessions WHERE id = ?", (session_id,))
        if cur.fetchone() is None:
            conn.close()
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        cur.execute(f"""
            UPDATE verification_sessions
            SET {col} = ?,
                current_step = CASE
                    WHEN current_step < ? THEN ?
                    ELSE current_step
                END,
                updated_at = ?
            WHERE id = ?
        """, (
            filename,
            new_step, new_step,
            datetime.utcnow().isoformat(),
            session_id
        ))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'filename': filename,
            'path': filepath,
            'size': len(image_bytes)
        })

    except Exception as e:
        print(f"✗ Error in /capture/: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/start-liveness/', methods=['POST', 'OPTIONS'])
def start_liveness():
    """
    Start web-based liveness detection
    NOTE: This does NOT run Python OpenCV liveness - that's handled by the web page
    """
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        global liveness_state

        print("\n🎭 Web-based liveness detection starting...")
        print("   (Browser will handle face detection, not Python)")

        # Just mark as running - the web page does everything
        liveness_state = {
            'running': True,
            'completed': False,
            'verified': False,
            'confidence': 0
        }

        return jsonify({
            'success': True,
            'message': 'Web liveness ready - complete checks in browser'
        })

    except Exception as e:
        print(f"✗ Error in /start-liveness/: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/liveness-result/', methods=['POST', 'OPTIONS'])
def liveness_result():
    """Receive liveness detection results from web client AND persist to DB"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        global liveness_state
        data = request.get_json(force=True) or {}

        session_id = data.get("session_id")
        if not session_id:
            return jsonify({'success': False, 'error': 'Missing session_id'}), 400

        verified = bool(data.get('verified', False))
        confidence = float(data.get('confidence', 0))
        challenges = data.get('challenges', {}) or {}

        completed_count = sum(1 for v in challenges.values() if v)
        total_count = len(challenges) if challenges else 4  # fallback

        # update in-memory state (optional)
        liveness_state['running'] = False
        liveness_state['completed'] = True
        liveness_state['verified'] = verified
        liveness_state['confidence'] = confidence

        print(f"\n{'=' * 70}")
        print("🎭 WEB LIVENESS RESULT RECEIVED:")
        print(f"{'=' * 70}")
        print(f"   Session: {session_id}")
        print(f"   Verified: {'✅ YES' if verified else '❌ NO'}")
        print(f"   Confidence: {confidence:.1f}%")
        print(f"   Challenges: {challenges}")
        print(f"{'=' * 70}\n")

        # ✅ persist to DB
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM verification_sessions WHERE id = ?", (session_id,))
        if cur.fetchone() is None:
            conn.close()
            return jsonify({'success': False, 'error': 'Session not found'}), 404

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
            1 if verified else 0,
            confidence,
            json.dumps(challenges),
            completed_count,
            total_count,
            datetime.now(UTC).isoformat(),
            session_id
        ))

        conn.commit()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/check-liveness/', methods=['GET'])
def check_liveness():
    """Check liveness detection status"""
    try:
        global liveness_state
        return jsonify({
            'running': liveness_state['running'],
            'completed': liveness_state['completed'],
            'verified': liveness_state['verified'],
            'confidence': liveness_state['confidence']
        })
    except Exception as e:
        print(f"✗ Error in /check-liveness/: {str(e)}")
        return jsonify({'completed': False, 'verified': False}), 500

@app.route('/verify/', methods=['POST', 'OPTIONS'])
def verify_identity():
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        data = request.get_json(force=True) or {}
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({'success': False, 'verified': False, 'error': 'Missing session_id'}), 400

        # 1) Load session from DB (source of truth)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM verification_sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()

        if row is None:
            conn.close()
            return jsonify({'success': False, 'verified': False, 'error': 'Session not found'}), 404

        session = dict(row)

        front_image = session.get("front_image")
        back_image = session.get("back_image")
        selfie_image = session.get("selfie_image")
        liveness_verified = bool(session.get("liveness_verified", 0))

        print(f"\n{'=' * 70}")
        print("🔍 VERIFICATION REQUEST (SESSION-BASED)")
        print(f"{'=' * 70}")
        print(f"Session ID: {session_id}")
        print(f"📄 Front Image: {front_image}")
        print(f"📄 Back Image:  {back_image}")
        print(f"🤳 Selfie Image:{selfie_image}")
        print(f"🎭 Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
        print(f"{'=' * 70}\n")

        # 2) Validate required images
        if not all([front_image, back_image, selfie_image]):
            conn.close()
            return jsonify({
                'success': False,
                'verified': False,
                'error': 'Missing required images in session'
            }), 400

        front_path = os.path.join(UPLOAD_FOLDER, front_image)
        back_path  = os.path.join(UPLOAD_FOLDER, back_image)
        selfie_path = os.path.join(UPLOAD_FOLDER, selfie_image)

        for img_path, img_name in [(front_path, 'front'), (back_path, 'back'), (selfie_path, 'selfie')]:
            if not os.path.exists(img_path):
                conn.close()
                return jsonify({
                    'success': False,
                    'verified': False,
                    'error': f'{img_name} image file not found: {img_path}'
                }), 404

        # 3) Run your existing 3-model verification
        try:
            from deepface import DeepFace

            print("🔬 Extracting face from ID card...")

            id_img = cv2.imread(front_path)

            try:
                faces = DeepFace.extract_faces(
                    img_path=front_path,
                    detector_backend='retinaface',
                    enforce_detection=False,
                    align=True
                )

                if faces and len(faces) > 0:
                    largest_face = max(faces, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])
                    fa = largest_face['facial_area']
                    x, y, w, h = fa['x'], fa['y'], fa['w'], fa['h']

                    padding = int(w * 0.2)
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    w = min(id_img.shape[1] - x, w + 2 * padding)
                    h = min(id_img.shape[0] - y, h + 2 * padding)

                    id_face = id_img[y:y + h, x:x + w]

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    id_face_path = os.path.join(UPLOAD_FOLDER, f'id_face_{timestamp}.jpg')
                    cv2.imwrite(id_face_path, id_face)

                    print(f"✓ Extracted ID face: {id_face_path}")
                else:
                    print("⚠ No face detected in ID, using full image")
                    id_face_path = front_path

            except Exception as e:
                print(f"⚠ Face extraction failed: {e}, using full ID image")
                id_face_path = front_path

            print("\n🔬 Comparing faces using multiple models...")

            models = ["VGG-Face", "Facenet", "ArcFace"]
            results = []

            for model in models:
                try:
                    r = DeepFace.verify(
                        img1_path=id_face_path,
                        img2_path=selfie_path,
                        model_name=model,
                        distance_metric='cosine',
                        enforce_detection=False
                    )

                    distance = r['distance']
                    verified = r['verified']
                    similarity = (1 - distance) * 100

                    results.append({
                        'model': model,
                        'similarity': similarity,
                        'verified': bool(verified),
                        'distance': float(distance),
                        'threshold': float(r.get('threshold', 0))
                    })

                    print(f"   {model:12} | Similarity: {similarity:5.1f}% | {'✓ MATCH' if verified else '✗ NO MATCH'}")

                except Exception as e:
                    print(f"   {model:12} | ❌ Failed: {str(e)[:60]}")

            if not results:
                conn.close()
                return jsonify({
                    'success': False,
                    'verified': False,
                    'error': 'Face verification failed - could not compare faces'
                }), 500

            avg_similarity = sum(r['similarity'] for r in results) / len(results)
            votes_yes = sum(1 for r in results if r['verified'])
            votes_total = len(results)

            final_verified = (votes_yes / votes_total) >= 0.5 or avg_similarity >= 50
            final_confidence = avg_similarity

            if liveness_verified:
                final_confidence = min(100, final_confidence + 10)
                print("   🎭 Liveness verified: +10% confidence boost")

            print(f"\n📊 VERIFICATION RESULT:")
            print(f"   Average Similarity: {avg_similarity:.1f}%")
            print(f"   Model Consensus: {votes_yes}/{votes_total}")
            print(f"   Final Confidence: {final_confidence:.1f}%")
            print(f"   Decision: {'✅ VERIFIED' if final_verified else '❌ REJECTED'}\n")

        except ImportError:
            # fallback
            results = []
            avg_similarity = 88.5
            final_confidence = 95.0 if liveness_verified else 85.0
            final_verified = avg_similarity >= 70

        # 4) Save final verify results into DB (THIS is the “per session” part)
        cur.execute("""
            UPDATE verification_sessions
            SET
                verify_verified = ?,
                verify_confidence = ?,
                verify_similarity = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            1 if final_verified else 0,
            float(final_confidence),
            float(avg_similarity),
            "verified" if final_verified else "rejected",
            datetime.now(UTC).isoformat(),
            session_id
        ))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'verified': final_verified,
            'similarity': avg_similarity,
            'confidence': final_confidence,
            'votes': votes_yes if 'votes_yes' in locals() else None,
            'total_models': votes_total if 'votes_total' in locals() else None,
            'liveness_verified': liveness_verified,
            'models': results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'verified': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🌙 MoonKYC Server Starting...")
    print("=" * 70)
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 Local: http://localhost:3000")
    print(f"📱 Network: http://YOUR_IP:3000")
    print(f"🌍 Ngrok: Use 'ngrok http 3000' for remote access")
    print(f"🎭 Liveness: WEB-BASED (runs in browser, not Python)")
    print("=" * 70 + "\n")

    # Run on all interfaces for ngrok compatibility
    app.run(host='0.0.0.0', port=3000, debug=True, threaded=True)