from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import os
import cv2
import numpy as np
import base64
from datetime import datetime
import subprocess
import time

# Global variable to track liveness process
liveness_process = None


def index(request):
    """Render the main KYC verification page"""
    return render(request, 'kyc/index.html')


@csrf_exempt
def start_liveness(request):
    """
    Launches the Python liveness detection script
    Endpoint: /start-liveness/
    """
    global liveness_process

    if request.method == 'POST':
        try:
            # Clean up any old result file
            result_file = 'liveness_result.json'
            if os.path.exists(result_file):
                os.remove(result_file)
                print("✓ Cleaned up old liveness result")

            # Get the path to liveness_detection.py
            # Adjust this path to match your project structure
            current_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(current_dir, '..', 'liveness_detection.py')

            # Alternative: Use absolute path if the above doesn't work
            # script_path = '/full/path/to/your/liveness_detection.py'

            if not os.path.exists(script_path):
                return JsonResponse({
                    'success': False,
                    'error': f'liveness_detection.py not found at {script_path}'
                }, status=404)

            print(f"Starting liveness detection: {script_path}")

            # Launch liveness detection in a subprocess
            # For Windows
            if os.name == 'nt':
                liveness_process = subprocess.Popen(
                    ['python', script_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            # For Mac/Linux
            else:
                liveness_process = subprocess.Popen(
                    ['python3', script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

            print(f"✓ Liveness detection started with PID: {liveness_process.pid}")

            return JsonResponse({
                'success': True,
                'message': 'Liveness detection started',
                'pid': liveness_process.pid
            })

        except FileNotFoundError:
            return JsonResponse({
                'success': False,
                'error': 'Python interpreter or liveness_detection.py not found. Please check the file path.'
            }, status=404)

        except Exception as e:
            print(f"❌ Error starting liveness: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Failed to start liveness detection: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method. Use POST.'
    }, status=405)


@csrf_exempt
def check_liveness(request):
    """
    Polls for liveness detection results
    Endpoint: /check-liveness/
    """
    try:
        result_file = 'liveness_result.json'

        # Check if the result file exists
        if os.path.exists(result_file):
            print(f"✓ Found liveness result file")

            # Read the result
            with open(result_file, 'r') as f:
                result = json.load(f)

            print(f"Liveness result: {result}")

            # Clean up the file after reading
            try:
                os.remove(result_file)
                print("✓ Liveness result file cleaned up")
            except Exception as e:
                print(f"⚠️ Could not remove result file: {e}")

            return JsonResponse({
                'completed': True,
                'verified': result.get('verified', False),
                'confidence': result.get('confidence', 0),
                'challenges': result.get('challenges', {}),
                'timestamp': result.get('timestamp', time.time())
            })
        else:
            # Still processing
            return JsonResponse({
                'completed': False,
                'message': 'Liveness detection in progress...'
            })

    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {str(e)}")
        return JsonResponse({
            'completed': False,
            'error': f'Invalid JSON in result file: {str(e)}'
        }, status=500)

    except Exception as e:
        print(f"❌ Error checking liveness: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'completed': False,
            'error': f'Failed to check liveness status: {str(e)}'
        }, status=500)


@csrf_exempt
def cancel_liveness(request):
    """
    Cancels the running liveness detection process
    Endpoint: /cancel-liveness/
    """
    global liveness_process

    if request.method == 'POST':
        try:
            # Terminate the process if it's running
            if liveness_process and liveness_process.poll() is None:
                liveness_process.terminate()
                try:
                    liveness_process.wait(timeout=5)
                    print("✓ Liveness process terminated gracefully")
                except subprocess.TimeoutExpired:
                    liveness_process.kill()
                    print("⚠️ Liveness process killed forcefully")
            else:
                print("⚠️ No active liveness process to cancel")

            # Clean up result file
            result_file = 'liveness_result.json'
            if os.path.exists(result_file):
                os.remove(result_file)
                print("✓ Cleaned up liveness result file")

            return JsonResponse({
                'success': True,
                'message': 'Liveness detection cancelled'
            })

        except Exception as e:
            print(f"❌ Error cancelling liveness: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to cancel liveness: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method. Use POST.'
    }, status=405)


@csrf_exempt
def capture_document(request):
    """Handle document capture from camera"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image')
            doc_type = data.get('type')

            if not image_data or not doc_type:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing image data or document type'
                }, status=400)

            # Decode base64 image
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)

            # Convert to numpy array for OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Basic quality checks
            quality_check = check_image_quality(img)
            if not quality_check['passed']:
                return JsonResponse({
                    'success': False,
                    'error': quality_check['message']
                }, status=400)

            # Save image
            os.makedirs('documents/captured', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"documents/captured/{doc_type}_{timestamp}.jpg"

            # Save with higher quality for better face detection
            cv2.imwrite(filename, img, [cv2.IMWRITE_JPEG_QUALITY, 95])

            print(f"✓ Saved {doc_type}: {filename}")

            return JsonResponse({
                'success': True,
                'filename': filename,
                'type': doc_type,
                'quality': quality_check
            })

        except Exception as e:
            print(f"❌ Capture error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only POST requests allowed'}, status=400)


@csrf_exempt
def verify_kyc(request):
    """Process complete KYC verification"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            front_path = data.get('front_image')
            back_path = data.get('back_image')
            selfie_path = data.get('selfie_image')
            liveness_verified = data.get('liveness_verified', False)  # NEW: Get liveness status

            print(f"\n{'=' * 70}")
            print("Starting KYC Verification...")
            print(f"Front: {front_path}")
            print(f"Back: {back_path}")
            print(f"Selfie: {selfie_path}")
            print(f"Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
            print(f"{'=' * 70}\n")

            if not all([front_path, back_path, selfie_path]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required images'
                }, status=400)

            # Check if files exist
            if not os.path.exists(front_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Front image not found: {front_path}'
                }, status=400)

            if not os.path.exists(selfie_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Selfie image not found: {selfie_path}'
                }, status=400)

            # Import DeepFace here
            from deepface import DeepFace

            print("Step 1: Extracting face from ID card...")

            # Extract face from ID card
            try:
                faces = DeepFace.extract_faces(
                    img_path=front_path,
                    detector_backend='opencv',
                    enforce_detection=False,
                    align=True
                )

                if not faces or len(faces) == 0:
                    print("❌ No face detected in ID card")
                    return JsonResponse({
                        'success': False,
                        'error': 'No face found in ID card. Please ensure the photo on the ID is clear and visible.'
                    }, status=400)

                print(f"✓ Found {len(faces)} face(s) in ID")

                # Get the largest face
                largest_face = max(faces, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])

                # Save extracted face
                doc_image = cv2.imread(front_path)
                facial_area = largest_face['facial_area']
                x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']

                # Add padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(doc_image.shape[1] - x, w + 2 * padding)
                h = min(doc_image.shape[0] - y, h + 2 * padding)

                id_face = doc_image[y:y + h, x:x + w]

                # Save ID face
                os.makedirs('documents/extracted_faces', exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                id_face_path = f"documents/extracted_faces/id_face_{timestamp}.jpg"
                cv2.imwrite(id_face_path, id_face, [cv2.IMWRITE_JPEG_QUALITY, 95])

                print(f"✓ Extracted ID face: {id_face_path}")

            except Exception as e:
                print(f"❌ Face extraction failed: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Could not extract face from ID: {str(e)}'
                }, status=400)

            print("\nStep 2: Comparing faces...")

            # Compare faces
            try:
                models = ["VGG-Face", "Facenet"]
                results = []

                for model in models:
                    print(f"Running {model}...")
                    result = DeepFace.verify(
                        img1_path=id_face_path,
                        img2_path=selfie_path,
                        model_name=model,
                        enforce_detection=False
                    )

                    distance = result['distance']
                    similarity = (1 - distance) * 100
                    verified = result['verified']

                    results.append({
                        'model': model,
                        'similarity': similarity,
                        'verified': verified,
                        'distance': distance
                    })

                    status = "✓ MATCH" if verified else "✗ NO MATCH"
                    print(f"  {model}: {similarity:.1f}% - {status}")

                # Calculate final decision
                votes_yes = sum(1 for r in results if r['verified'])
                avg_similarity = sum(r['similarity'] for r in results) / len(results)
                final_match = votes_yes >= 1  # At least 1 model says match

                print(f"\n{'=' * 70}")
                print(f"VERIFICATION RESULT:")
                print(f"  Average Similarity: {avg_similarity:.1f}%")
                print(f"  Models Agree: {votes_yes}/{len(results)}")
                print(f"  Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
                print(f"  Final Decision: {'✅ VERIFIED' if final_match else '❌ REJECTED'}")
                print(f"{'=' * 70}\n")

                return JsonResponse({
                    'success': True,
                    'verified': final_match,
                    'similarity': avg_similarity,
                    'confidence': avg_similarity,
                    'votes': votes_yes,
                    'total_models': len(results),
                    'liveness_verified': liveness_verified,  # NEW: Include liveness status
                    'details': {
                        'id_face_path': id_face_path,
                        'models': results,
                        'liveness_status': 'verified' if liveness_verified else 'skipped'
                    }
                })

            except Exception as e:
                print(f"❌ Face comparison failed: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Face comparison failed: {str(e)}'
                }, status=500)

        except Exception as e:
            print(f"❌ Verification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only POST requests allowed'}, status=400)


def check_image_quality(img):
    """Check if image quality is acceptable"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)

    if brightness < 40:
        return {
            'passed': False,
            'message': 'Image too dark. Please ensure good lighting.',
            'brightness': float(brightness)
        }

    if brightness > 220:
        return {
            'passed': False,
            'message': 'Image too bright. Reduce lighting or avoid glare.',
            'brightness': float(brightness)
        }

    # Check for blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    if laplacian_var < 50:  # Lowered threshold for mobile cameras
        return {
            'passed': False,
            'message': 'Image is blurry. Please hold steady and focus.',
            'sharpness': float(laplacian_var)
        }

    return {
        'passed': True,
        'message': 'Image quality is good',
        'brightness': float(brightness),
        'sharpness': float(laplacian_var)
    }