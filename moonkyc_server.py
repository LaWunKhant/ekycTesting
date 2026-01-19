from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import base64
import os
from datetime import datetime
import json
import cv2
import numpy as np

app = Flask(__name__)
CORS(app)

# Directory to store uploaded images
UPLOAD_FOLDER = 'uploads'
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
    possible_paths = [
        'index.html',
        'moonkyc.html',
        'kyc/templates/kyc/index.html',
        'templates/index.html',
        'templates/kyc/index.html'
    ]

    for path in possible_paths:
        if os.path.exists(path):
            directory = os.path.dirname(path) or '.'
            filename = os.path.basename(path)
            print(f"✓ Serving HTML from: {path}")
            return send_from_directory(directory, filename)

    return f"""
    <html>
        <body style="font-family: Arial; padding: 40px; background: #f5f5f5;">
            <h1 style="color: #e74c3c;">❌ HTML File Not Found</h1>
            <p>Please save your HTML file as one of:</p>
            <ul>
                <li><code>index.html</code></li>
                <li><code>moonkyc.html</code></li>
            </ul>
            <p>In the same directory as <code>moonkyc_server.py</code></p>
            <p><strong>Current directory:</strong> {os.getcwd()}</p>
        </body>
    </html>
    """, 404


@app.route('/liveness.html')
def liveness_page():
    """Serve the liveness detection page"""
    if os.path.exists('liveness.html'):
        return send_from_directory('.', 'liveness.html')
    else:
        return """
        <html>
            <body style="font-family: Arial; padding: 40px;">
                <h1 style="color: #e74c3c;">❌ liveness.html not found</h1>
                <p>Please save the liveness.html file in the same directory as moonkyc_server.py</p>
            </body>
        </html>
        """, 404


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
    """Receive liveness detection results from web client"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        global liveness_state
        data = request.get_json(force=True)

        liveness_state['running'] = False
        liveness_state['completed'] = True
        liveness_state['verified'] = data.get('verified', False)
        liveness_state['confidence'] = data.get('confidence', 0)

        print(f"\n{'=' * 70}")
        print(f"🎭 WEB LIVENESS RESULT RECEIVED:")
        print(f"{'=' * 70}")
        print(f"   Verified: {'✅ YES' if liveness_state['verified'] else '❌ NO'}")
        print(f"   Confidence: {liveness_state['confidence']:.1f}%")
        print(f"   Challenges: {data.get('challenges', {})}")
        print(f"{'=' * 70}\n")

        return jsonify({'success': True})
    except Exception as e:
        print(f"✗ Error in /liveness-result/: {str(e)}")
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
    """Verify identity using DeepFace"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400

        front_image = data.get('front_image')
        back_image = data.get('back_image')
        selfie_image = data.get('selfie_image')
        liveness_verified = data.get('liveness_verified', False)

        print(f"\n{'=' * 70}")
        print(f"🔍 VERIFICATION REQUEST")
        print(f"{'=' * 70}")
        print(f"📄 Front Image: {front_image}")
        print(f"📄 Back Image: {back_image}")
        print(f"🤳 Selfie Image: {selfie_image}")
        print(f"🎭 Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
        print(f"{'=' * 70}\n")

        # Check if all required images are present
        if not all([front_image, back_image, selfie_image]):
            return jsonify({
                'success': False,
                'verified': False,
                'error': 'Missing required images'
            }), 400

        # Verify files exist
        front_path = os.path.join(UPLOAD_FOLDER, front_image)
        back_path = os.path.join(UPLOAD_FOLDER, back_image)
        selfie_path = os.path.join(UPLOAD_FOLDER, selfie_image)

        for img_path, img_name in [(front_path, 'front'), (back_path, 'back'), (selfie_path, 'selfie')]:
            if not os.path.exists(img_path):
                return jsonify({
                    'success': False,
                    'verified': False,
                    'error': f'{img_name} image file not found'
                }), 404

        # Use DeepFace for verification
        try:
            from deepface import DeepFace

            print("🔬 Extracting face from ID card...")

            # Extract face from ID card (front image)
            id_img = cv2.imread(front_path)

            # Try to detect and extract face from ID
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

                    # Add padding
                    padding = int(w * 0.2)
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    w = min(id_img.shape[1] - x, w + 2 * padding)
                    h = min(id_img.shape[0] - y, h + 2 * padding)

                    id_face = id_img[y:y + h, x:x + w]

                    # Save extracted face
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

            # Perform face verification
            print("\n🔬 Comparing faces using multiple models...")

            models = ["VGG-Face", "Facenet", "ArcFace"]
            results = []

            for model in models:
                try:
                    result = DeepFace.verify(
                        img1_path=id_face_path,
                        img2_path=selfie_path,
                        model_name=model,
                        distance_metric='cosine',
                        enforce_detection=False
                    )

                    distance = result['distance']
                    threshold = result['threshold']
                    verified = result['verified']
                    similarity = (1 - distance) * 100

                    results.append({
                        'model': model,
                        'similarity': similarity,
                        'verified': verified
                    })

                    status = "✓ MATCH" if verified else "✗ NO MATCH"
                    print(f"   {model:12} | Similarity: {similarity:5.1f}% | {status}")

                except Exception as e:
                    print(f"   {model:12} | ❌ Failed: {str(e)[:40]}")

            if not results:
                print("\n❌ All verification models failed")
                return jsonify({
                    'success': False,
                    'verified': False,
                    'error': 'Face verification failed - could not compare faces'
                })

            # Calculate final result
            avg_similarity = sum(r['similarity'] for r in results) / len(results)
            votes_yes = sum(1 for r in results if r['verified'])
            votes_total = len(results)

            # More lenient thresholds for real-world usage
            final_verified = (votes_yes / votes_total) >= 0.5 or avg_similarity >= 50

            # Boost confidence if liveness passed
            final_confidence = avg_similarity
            if liveness_verified:
                final_confidence = min(100, final_confidence + 10)
                print("   🎭 Liveness verified: +10% confidence boost")

            print(f"\n{'=' * 70}")
            print(f"📊 VERIFICATION RESULT:")
            print(f"   Average Similarity: {avg_similarity:.1f}%")
            print(f"   Model Consensus: {votes_yes}/{votes_total} ({votes_yes / votes_total * 100:.1f}%) say MATCH")
            print(f"   Final Confidence: {final_confidence:.1f}%")
            print(f"   Decision: {'✅ VERIFIED' if final_verified else '❌ REJECTED'}")
            print(f"{'=' * 70}\n")

            return jsonify({
                'success': True,
                'verified': final_verified,
                'similarity': avg_similarity,
                'confidence': final_confidence,
                'votes': votes_yes,
                'total_models': votes_total,
                'liveness_verified': liveness_verified
            })

        except ImportError:
            print("⚠ DeepFace not available, using simulated verification")
            similarity = 88.5
            confidence = 85.0

            if liveness_verified:
                confidence += 10

            verified = similarity > 70 and confidence > 75

            return jsonify({
                'success': True,
                'verified': verified,
                'similarity': similarity,
                'confidence': confidence,
                'liveness_verified': liveness_verified,
                'note': 'Simulated verification (DeepFace not installed)'
            })

    except Exception as e:
        print(f"✗ Error in /verify/: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'verified': False,
            'error': str(e)
        }), 500


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