import cv2
import os
import numpy as np
from datetime import datetime
from document_scanner import SimpleDocumentScanner
from deepface import DeepFace


class ImprovedEKYC:
    def __init__(self):
        self.scanner = SimpleDocumentScanner()
        self.results = {}

    def preprocess_face(self, face_img):
        """
        Preprocessing to improve face recognition accuracy
        """
        # 1. Resize to standard size for consistency
        face_img = cv2.resize(face_img, (224, 224))

        # 2. Histogram equalization for better lighting
        if len(face_img.shape) == 3:
            # Convert to YCrCb color space
            ycrcb = cv2.cvtColor(face_img, cv2.COLOR_BGR2YCrCb)
            # Equalize the Y channel
            ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
            # Convert back to BGR
            face_img = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        # 3. Denoise
        face_img = cv2.fastNlMeansDenoisingColored(face_img, None, 10, 10, 7, 21)

        # 4. Sharpen
        kernel = np.array([[-1, -1, -1],
                           [-1, 9, -1],
                           [-1, -1, -1]])
        face_img = cv2.filter2D(face_img, -1, kernel)

        return face_img

    def step1_document_capture(self):
        """Step 1: Capture documents"""
        print("\n" + "=" * 70)
        print(" " * 20 + "STEP 1: DOCUMENT CAPTURE")
        print("=" * 70)

        captures = self.scanner.run()

        if not captures:
            print("❌ Document capture failed")
            return False

        self.results['captures'] = captures
        return True

    def step2_extract_id_face(self):
        """Step 2: Extract face from ID card with improved preprocessing"""
        print("\n" + "=" * 70)
        print(" " * 20 + "STEP 2: EXTRACT & ENHANCE ID FACE")
        print("=" * 70)

        captures = self.results.get('captures', {})

        # Find document with photo
        doc_image_path = None
        if 'front' in captures:
            doc_image_path = captures['front']['filename']
        elif 'photo_page' in captures:
            doc_image_path = captures['photo_page']['filename']

        if doc_image_path is None:
            print("❌ No document image found")
            return False

        print(f"📄 Analyzing: {doc_image_path}")

        try:
            # Load original document image
            doc_image = cv2.imread(doc_image_path)

            # Enhance document image before face detection
            enhanced_doc = self.enhance_document_image(doc_image)

            # Save enhanced document temporarily
            temp_enhanced = "temp_enhanced_doc.jpg"
            cv2.imwrite(temp_enhanced, enhanced_doc)

            # Detect faces with multiple backends for better detection
            faces = None
            backends = ['retinaface', 'mtcnn', 'opencv']

            for backend in backends:
                try:
                    faces = DeepFace.extract_faces(
                        img_path=temp_enhanced,
                        detector_backend=backend,
                        enforce_detection=False,
                        align=True  # Align face for better recognition
                    )
                    if faces and len(faces) > 0:
                        print(f"✓ Detected faces using {backend}")
                        break
                except:
                    continue

            # Clean up temp file
            if os.path.exists(temp_enhanced):
                os.remove(temp_enhanced)

            if not faces:
                print("❌ No face found in document")
                return False

            print(f"✓ Found {len(faces)} face(s) in document")

            # Get the largest face with highest confidence
            valid_faces = [f for f in faces if f.get('confidence', 0) > 0.8]
            if not valid_faces:
                valid_faces = faces

            largest_face = max(valid_faces, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])

            # Extract face with more padding
            facial_area = largest_face['facial_area']
            x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']

            # Increase padding for better context
            padding_x = int(w * 0.3)
            padding_y = int(h * 0.4)

            x = max(0, x - padding_x)
            y = max(0, y - padding_y)
            w = min(enhanced_doc.shape[1] - x, w + 2 * padding_x)
            h = min(enhanced_doc.shape[0] - y, h + 2 * padding_y)

            id_face_raw = enhanced_doc[y:y + h, x:x + w]

            # Preprocess the extracted face
            id_face = self.preprocess_face(id_face_raw)

            # Save both raw and processed versions
            os.makedirs('documents/extracted_faces', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            face_raw_filename = f"documents/extracted_faces/id_face_raw_{timestamp}.jpg"
            face_processed_filename = f"documents/extracted_faces/id_face_processed_{timestamp}.jpg"

            cv2.imwrite(face_raw_filename, id_face_raw)
            cv2.imwrite(face_processed_filename, id_face)

            self.results['id_face'] = {
                'image': id_face,
                'filename': face_processed_filename,
                'raw_filename': face_raw_filename,
                'location': facial_area
            }

            print(f"✓ Extracted & enhanced ID face")
            print(f"   Raw: {face_raw_filename}")
            print(f"   Enhanced: {face_processed_filename}")
            print(f"   Face size: {w}x{h} pixels")

            # Show comparison
            comparison = np.hstack([
                cv2.resize(id_face_raw, (200, 250)),
                cv2.resize(id_face, (200, 250))
            ])
            cv2.imshow('ID Face: Raw vs Enhanced - Press any key', comparison)
            cv2.waitKey(2000)
            cv2.destroyAllWindows()

            return True

        except Exception as e:
            print(f"❌ Face extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def enhance_document_image(self, img):
        """Enhance document image quality"""
        # Increase contrast
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        # Sharpen
        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]])
        enhanced = cv2.filter2D(enhanced, -1, kernel)

        return enhanced

    def step2_5_liveness_detection(self):
        """Step 2.5: Verify liveness before face comparison"""
        print("\n" + "=" * 70)
        print(" " * 20 + "STEP 2.5: LIVENESS DETECTION")
        print("=" * 70)

        from liveness_detection import LivenessDetector

        liveness_detector = LivenessDetector()
        is_live = liveness_detector.verify_liveness()

        if is_live:
            print("✅ Liveness verified - Real person detected")
            self.results['liveness'] = {
                'verified': True,
                'confidence': liveness_detector.confidence
            }
            return True
        else:
            print("❌ Liveness failed - Possible spoofing detected")
            self.results['liveness'] = {
                'verified': False,
                'reason': 'Failed liveness checks'
            }
            return False

    def step3_face_comparison(self):
        """Step 3: Compare ID face with selfie using multiple models"""
        print("\n" + "=" * 70)
        print(" " * 20 + "STEP 3: ADVANCED FACE VERIFICATION")
        print("=" * 70)

        captures = self.results.get('captures', {})
        id_face_data = self.results.get('id_face')

        if not id_face_data or 'selfie' not in captures:
            print("❌ Missing required images for comparison")
            return False

        # Preprocess selfie too
        selfie_raw = cv2.imread(captures['selfie']['filename'])

        # Detect and extract face from selfie with alignment
        try:
            selfie_faces = DeepFace.extract_faces(
                img_path=captures['selfie']['filename'],
                detector_backend='retinaface',
                enforce_detection=False,
                align=True
            )

            if selfie_faces and len(selfie_faces) > 0:
                largest_selfie = max(selfie_faces, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])
                fa = largest_selfie['facial_area']
                x, y, w, h = fa['x'], fa['y'], fa['w'], fa['h']

                # Add padding
                padding = int(w * 0.2)
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(selfie_raw.shape[1] - x, w + 2 * padding)
                h = min(selfie_raw.shape[0] - y, h + 2 * padding)

                selfie_face = selfie_raw[y:y + h, x:x + w]
                selfie_processed = self.preprocess_face(selfie_face)

                # Save processed selfie
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                selfie_processed_path = f"documents/extracted_faces/selfie_processed_{timestamp}.jpg"
                cv2.imwrite(selfie_processed_path, selfie_processed)

                selfie_path = selfie_processed_path
                print("✓ Preprocessed selfie for better comparison")
            else:
                selfie_path = captures['selfie']['filename']
                print("⚠ Using original selfie (face detection failed)")

        except Exception as e:
            print(f"⚠ Selfie preprocessing failed: {e}")
            selfie_path = captures['selfie']['filename']

        id_face_path = id_face_data['filename']

        print(f"\n📊 Comparing faces:")
        print(f"   ID Face: {id_face_path}")
        print(f"   Selfie:  {selfie_path}\n")

        try:
            # Use more models for robust verification
            models = ["VGG-Face", "Facenet", "ArcFace", "DeepFace"]
            distance_metrics = ["cosine", "euclidean"]
            results = []

            print("Running comprehensive face recognition analysis...\n")

            for model in models:
                for metric in distance_metrics:
                    try:
                        result = DeepFace.verify(
                            img1_path=id_face_path,
                            img2_path=selfie_path,
                            model_name=model,
                            distance_metric=metric,
                            enforce_detection=False
                        )

                        distance = result['distance']
                        threshold = result['threshold']
                        verified = result['verified']

                        # Calculate similarity percentage
                        if metric == "cosine":
                            similarity = (1 - distance) * 100
                        else:  # euclidean
                            # Normalize euclidean distance to percentage
                            similarity = max(0, (1 - (distance / threshold)) * 100)

                        results.append({
                            'model': model,
                            'metric': metric,
                            'similarity': similarity,
                            'verified': verified,
                            'distance': distance,
                            'threshold': threshold
                        })

                        status = "✓ MATCH" if verified else "✗ NO MATCH"
                        print(f"   {model:12} ({metric:9}) | Sim: {similarity:5.1f}% | {status}")
                    except Exception as e:
                        print(f"   {model:12} ({metric:9}) | ❌ Failed: {str(e)[:30]}")

            if not results:
                print("\n❌ All face comparison models failed")
                return False

            # Calculate final decision with weighted voting
            votes_yes = sum(1 for r in results if r['verified'])
            votes_total = len(results)
            avg_similarity = sum(r['similarity'] for r in results) / len(results)

            # Require 60% consensus for match
            consensus_threshold = 0.6
            final_match = (votes_yes / votes_total) >= consensus_threshold

            print(f"\n" + "-" * 70)
            print(f"COMPREHENSIVE VERIFICATION RESULT:")
            print(f"   Average Similarity: {avg_similarity:.1f}%")
            print(f"   Model Consensus: {votes_yes}/{votes_total} ({votes_yes / votes_total * 100:.1f}%) say MATCH")
            print(
                f"   Confidence Level: {'HIGH' if avg_similarity > 70 else 'MEDIUM' if avg_similarity > 60 else 'LOW'}")

            if final_match:
                print(f"   Decision: ✅ VERIFIED - Same person")
            else:
                print(f"   Decision: ❌ REJECTED - Different person or insufficient confidence")
            print("-" * 70)

            self.results['verification'] = {
                'verified': final_match,
                'similarity': avg_similarity,
                'votes': votes_yes,
                'total_models': votes_total,
                'consensus': votes_yes / votes_total,
                'details': results
            }

            return final_match

        except Exception as e:
            print(f"❌ Face comparison failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def step4_generate_report(self):
        """Step 4: Generate final report"""
        print("\n" + "=" * 70)
        print(" " * 25 + "📋 FINAL eKYC REPORT")
        print("=" * 70)

        captures = self.results.get('captures', {})
        verification = self.results.get('verification', {})

        # Document info
        doc_count = len([k for k in captures.keys() if k != 'selfie'])
        print(f"\n✓ Documents captured: {doc_count}")
        for key in captures:
            if key != 'selfie':
                print(f"   - {key}: {captures[key]['filename']}")

        # Selfie info
        if 'selfie' in captures:
            print(f"\n✓ Selfie captured: {captures['selfie']['filename']}")

        # Face extraction
        if 'id_face' in self.results:
            print(f"\n✓ ID face extracted and enhanced")

        # Liveness
        liveness = self.results.get('liveness', {})
        if liveness:
            status = "✓ Verified" if liveness.get('verified') else "✗ Failed"
            print(f"\n✓ Liveness Detection: {status}")

        # Verification result
        if verification:
            print(f"\n{'=' * 70}")
            if verification['verified']:
                print("✅ VERIFICATION STATUS: PASSED")
                print(f"   Identity confirmed with {verification['similarity']:.1f}% confidence")
                print(f"   Model consensus: {verification['consensus'] * 100:.1f}%")
            else:
                print("❌ VERIFICATION STATUS: FAILED")
                print(f"   Identity could not be confirmed ({verification['similarity']:.1f}% confidence)")
                print(f"   Model consensus: {verification['consensus'] * 100:.1f}%")
            print(f"{'=' * 70}\n")

        return verification.get('verified', False)

    def run(self):
        """Run complete improved eKYC workflow"""
        print("\n" + "=" * 70)
        print(" " * 10 + "🎯 IMPROVED eKYC VERIFICATION SYSTEM v2.0")
        print("=" * 70)
        print("\nEnhancements:")
        print("✓ Advanced image preprocessing")
        print("✓ Multiple face detection backends")
        print("✓ Enhanced face extraction with alignment")
        print("✓ Multi-model verification (8+ comparisons)")
        print("✓ Improved lighting normalization")
        print("\n" + "=" * 70)

        input("\nPress ENTER to start...")

        # Step 1: Capture documents and selfie
        if not self.step1_document_capture():
            print("\n❌ eKYC failed at document capture")
            return False

        # Step 2: Extract and enhance face from ID
        if not self.step2_extract_id_face():
            print("\n⚠️ Could not extract face from ID")
            print("❌ eKYC verification cannot proceed")
            return False

        # Step 2.5: Liveness Detection
        if not self.step2_5_liveness_detection():
            print("\n❌ Liveness verification failed")
            print("⚠️ eKYC verification cannot proceed")
            return False

        # Step 3: Compare faces with improved algorithm
        if not self.step3_face_comparison():
            print("\n❌ Face verification failed")

        # Step 4: Final report
        result = self.step4_generate_report()

        return result


if __name__ == "__main__":
    ekyc = ImprovedEKYC()
    success = ekyc.run()

    if success:
        print("\n" + "=" * 70)
        print("🎉 eKYC VERIFICATION COMPLETE!")
        print("✅ User identity successfully verified")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ eKYC VERIFICATION FAILED")
        print("⚠️ User identity could not be verified")
        print("=" * 70)