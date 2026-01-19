import cv2
import numpy as np
import dlib
from scipy.spatial import distance as dist
import time
import os
import urllib.request
import bz2
import json


def download_shape_predictor():
    filename = "shape_predictor_68_face_landmarks.dat"
    if os.path.exists(filename):
        return filename

    print("📥 Downloading facial landmark model (99.7 MB)...")
    url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
    compressed_file = filename + ".bz2"
    urllib.request.urlretrieve(url, compressed_file)
    print("✓ Downloaded!")

    print("📦 Extracting...")
    with bz2.open(compressed_file, 'rb') as source:
        with open(filename, 'wb') as dest:
            dest.write(source.read())
    os.remove(compressed_file)
    print("✓ Ready!")
    return filename


class LivenessDetector:
    """Main liveness detector class - called by moonekyc.py"""

    def __init__(self):
        self.detector = MouthDetectionLiveness()
        self.confidence = 0.0
        self.results = {}

    def verify_liveness(self):
        """Run liveness detection and return True/False"""
        success = self.detector.run()

        if success:
            self.confidence = self.detector.get_progress()
            self.results = {
                'challenges_completed': {
                    'center': self.detector.challenges['center']['completed'],
                    'left': self.detector.challenges['left']['completed'],
                    'right': self.detector.challenges['right']['completed'],
                    'mouth': self.detector.challenges['mouth']['completed']
                },
                'mouth_opens': self.detector.mouth_open_counter
            }
            return True
        else:
            self.confidence = self.detector.get_progress()
            return False

    def save_result(self, output_file='liveness_result.json'):
        """Save verification result to JSON file for Django to read"""
        result = {
            'verified': self.confidence == 100,
            'confidence': int(self.confidence),
            'timestamp': time.time(),
            'challenges': self.results.get('challenges_completed', {}),
            'mouth_opens': self.results.get('mouth_opens', 0)
        }

        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"\n✓ Results saved to {output_file}")
        return result


class MouthDetectionLiveness:
    def __init__(self):
        self.detector = dlib.get_frontal_face_detector()
        predictor_path = download_shape_predictor()
        self.predictor = dlib.shape_predictor(predictor_path)

        # Mouth landmarks
        self.MOUTH_OUTER = list(range(48, 60))
        self.MOUTH_INNER = list(range(60, 68))

        # IMPROVED: Lower threshold for easier detection
        self.MOUTH_AR_THRESH = 0.4
        self.mouth_open_frames = 0
        self.mouth_closed_frames = 0
        self.mouth_open_counter = 0
        self.mouth_is_open = False

        # IMPROVED: Simplified challenges
        self.challenges = {
            'center': {'completed': False, 'name': 'Look at the camera', 'frames': 0},
            'left': {'completed': False, 'name': 'Turn your head LEFT', 'frames': 0},
            'right': {'completed': False, 'name': 'Turn your head RIGHT', 'frames': 0},
            'mouth': {'completed': False, 'name': 'Open your mouth 2 times', 'frames': 0}
        }

        # IMPROVED: Reduced required opens
        self.REQUIRED_MOUTH_OPENS = 2

        # IMPROVED: Add frame requirements
        self.REQUIRED_FRAMES = {
            'center': 15,
            'left': 10,
            'right': 10,
        }

    def mouth_aspect_ratio(self, mouth):
        """Calculate mouth aspect ratio (MAR)"""
        A = dist.euclidean(mouth[2], mouth[10])
        B = dist.euclidean(mouth[3], mouth[9])
        C = dist.euclidean(mouth[4], mouth[8])
        D = dist.euclidean(mouth[0], mouth[6])

        if D == 0:
            return 0

        mar = (A + B + C) / (3.0 * D)
        return mar

    def get_landmarks(self, gray, rect):
        shape = self.predictor(gray, rect)
        coords = np.zeros((68, 2), dtype=int)
        for i in range(68):
            coords[i] = (shape.part(i).x, shape.part(i).y)
        return coords

    def detect_head_position(self, landmarks, frame_width):
        """IMPROVED: More sensitive head position detection"""
        nose_tip = landmarks[30]
        left_face = landmarks[0]
        right_face = landmarks[16]

        left_width = nose_tip[0] - left_face[0]
        right_width = right_face[0] - nose_tip[0]

        if right_width < 5:
            right_width = 5
        if left_width < 5:
            left_width = 5

        width_ratio = left_width / right_width
        nose_x = nose_tip[0]
        frame_center = frame_width // 2
        offset = nose_x - frame_center

        if width_ratio < 0.85 or offset < -20:
            return 'left'
        elif width_ratio > 1.15 or offset > 20:
            return 'right'
        else:
            return 'center'

    def get_progress(self):
        completed = sum(1 for c in self.challenges.values() if c['completed'])
        return int((completed / len(self.challenges)) * 100)

    def draw_mouth_region(self, frame, mouth_coords):
        """Draw mouth outline for visual feedback"""
        for i in range(len(mouth_coords)):
            cv2.line(frame,
                     tuple(mouth_coords[i]),
                     tuple(mouth_coords[(i + 1) % len(mouth_coords)]),
                     (0, 255, 255), 2)

    def detect_mouth_opening(self, mar):
        """IMPROVED: More reliable mouth opening detection"""
        if self.challenges['mouth']['completed']:
            return False

        if mar > self.MOUTH_AR_THRESH:
            self.mouth_open_frames += 1
            self.mouth_closed_frames = 0

            if self.mouth_open_frames >= 2 and not self.mouth_is_open:
                self.mouth_is_open = True
                print(f"👄 Mouth opened! (MAR: {mar:.2f})")
        else:
            self.mouth_closed_frames += 1

            if self.mouth_is_open and self.mouth_closed_frames >= 2:
                self.mouth_open_counter += 1
                self.mouth_is_open = False
                self.mouth_open_frames = 0
                print(f"✓ Mouth close detected! Count: {self.mouth_open_counter}/{self.REQUIRED_MOUTH_OPENS}")
                return True

            if not self.mouth_is_open:
                self.mouth_open_frames = 0

        return False

    def draw_direction_guides(self, frame, current_position):
        """IMPROVED: Better visual guides"""
        h, w = frame.shape[:2]

        if not self.challenges['left']['completed']:
            color = (0, 255, 0) if current_position == 'left' else (100, 100, 100)
            thickness = 10 if current_position == 'left' else 3
            cv2.arrowedLine(frame, (200, h // 2), (80, h // 2), color, thickness, tipLength=0.4)
            cv2.putText(frame, 'LEFT', (90, h // 2 + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        if not self.challenges['right']['completed']:
            color = (0, 255, 0) if current_position == 'right' else (100, 100, 100)
            thickness = 10 if current_position == 'right' else 3
            cv2.arrowedLine(frame, (w - 200, h // 2), (w - 80, h // 2), color, thickness, tipLength=0.4)
            cv2.putText(frame, 'RIGHT', (w - 200, h // 2 + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        if not self.challenges['center']['completed']:
            color = (0, 255, 0) if current_position == 'center' else (100, 100, 100)
            thickness = 8 if current_position == 'center' else 3
            cv2.circle(frame, (w // 2, h // 2), 40, color, thickness)
            cv2.putText(frame, 'CENTER', (w // 2 - 80, h // 2 - 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

    def draw_ui(self, frame, mar):
        """IMPROVED: Better UI with clearer instructions"""
        h, w = frame.shape[:2]

        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (w - 10, 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        progress = self.get_progress()
        bar_width = int((w - 40) * (progress / 100))
        cv2.rectangle(frame, (20, 20), (w - 20, 50), (50, 50, 50), -1)
        cv2.rectangle(frame, (20, 20), (20 + bar_width, 50), (0, 255, 0), -1)
        cv2.putText(frame, f'Progress: {progress}%', (w // 2 - 90, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        if not self.challenges['mouth']['completed']:
            mouth_y = 80
            if mar > self.MOUTH_AR_THRESH:
                mouth_status = "MOUTH: OPEN ✓"
                mouth_color = (0, 255, 0)
            else:
                mouth_status = "MOUTH: CLOSED"
                mouth_color = (200, 200, 200)

            cv2.putText(frame, mouth_status, (20, mouth_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, mouth_color, 2)

            cv2.putText(frame, f'Opens: {self.mouth_open_counter}/{self.REQUIRED_MOUTH_OPENS}',
                        (w - 200, mouth_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        y_offset = 130
        for key, challenge in self.challenges.items():
            if challenge['completed']:
                status = '✓'
                color = (0, 255, 0)
                text = f"{status} {challenge['name']} - DONE!"
            elif challenge['frames'] > 5:
                status = '→'
                color = (0, 255, 255)
                progress_percent = min(100, int((challenge['frames'] / self.REQUIRED_FRAMES.get(key, 10)) * 100))
                text = f"{status} {challenge['name']} ({progress_percent}%)"
            else:
                status = '○'
                color = (150, 150, 150)
                text = f"{status} {challenge['name']}"

            cv2.putText(frame, text, (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            y_offset += 40

        if progress < 100:
            current = next((c for c in self.challenges.values()
                            if not c['completed']), None)
            if current:
                pulse = int(abs(np.sin(time.time() * 3) * 100) + 155)
                instruction = current['name'].upper()
                cv2.putText(frame, f">>> {instruction} <<<",
                            (w // 2 - 300, h - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (pulse, 255, pulse), 4)
        else:
            cv2.putText(frame, "✓✓✓ ALL COMPLETE! ✓✓✓", (w // 2 - 250, h - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 4)

    def run(self):
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Cannot open camera")
            return False

        print("\n" + "=" * 70)
        print("🎥 IMPROVED eKYC Liveness Detection")
        print("=" * 70)
        print("Instructions:")
        print("1. Look at the center of the screen")
        print("2. Turn your head LEFT")
        print("3. Turn your head RIGHT")
        print("4. Open your mouth 2 times (naturally)")
        print("\nPress 'Q' to quit\n")

        start_time = time.time()
        no_face_start = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h, w = frame.shape[:2]

            rects = self.detector(gray, 0)
            current_position = 'none'

            if len(rects) == 1:
                no_face_start = None
                rect = rects[0]
                landmarks = self.get_landmarks(gray, rect)

                x, y = rect.left(), rect.top()
                w_face, h_face = rect.right() - x, rect.bottom() - y
                cv2.rectangle(frame, (x, y), (x + w_face, y + h_face), (0, 255, 0), 3)

                mouth = landmarks[self.MOUTH_OUTER]
                mar = self.mouth_aspect_ratio(mouth)

                self.draw_mouth_region(frame, mouth)

                if self.detect_mouth_opening(mar):
                    if self.mouth_open_counter >= self.REQUIRED_MOUTH_OPENS:
                        self.challenges['mouth']['completed'] = True
                        print("✓ Mouth challenge completed!")

                position = self.detect_head_position(landmarks, w)
                current_position = position

                for pos in ['center', 'left', 'right']:
                    required = self.REQUIRED_FRAMES.get(pos, 10)
                    if position == pos:
                        self.challenges[pos]['frames'] += 1
                        if self.challenges[pos]['frames'] >= required and not self.challenges[pos]['completed']:
                            self.challenges[pos]['completed'] = True
                            print(f"✓ {pos.capitalize()} confirmed!")
                    else:
                        self.challenges[pos]['frames'] = max(0, self.challenges[pos]['frames'] - 2)

                self.draw_ui(frame, mar)

            elif len(rects) == 0:
                if no_face_start is None:
                    no_face_start = time.time()

                cv2.putText(frame, "NO FACE DETECTED", (w // 2 - 200, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                cv2.putText(frame, "Please position your face in the frame", (w // 2 - 280, h // 2 + 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                cv2.putText(frame, "MULTIPLE FACES DETECTED", (w // 2 - 250, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

            self.draw_direction_guides(frame, current_position)

            if self.get_progress() == 100:
                elapsed = time.time() - start_time
                print(f"\n{'=' * 70}")
                print(f"✓✓✓ LIVENESS VERIFIED in {elapsed:.1f} seconds!")
                print(f"{'=' * 70}\n")
                cv2.putText(frame, "SUCCESS!", (w // 2 - 120, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 5)
                cv2.imshow('eKYC Liveness Verification', frame)
                cv2.waitKey(2000)
                break

            cv2.imshow('eKYC Liveness Verification', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("\n⚠️ User cancelled liveness detection")
                break

        cap.release()
        cv2.destroyAllWindows()

        return self.get_progress() == 100


if __name__ == "__main__":
    detector = LivenessDetector()
    success = detector.verify_liveness()

    # IMPORTANT: Save results for Django to read
    result = detector.save_result()

    if success:
        print("✓ LIVE user verified")
        print(f"✓ Confidence: {detector.confidence}%")
        print("✓ Ready for document scanning!")
    else:
        print("✗ Verification incomplete")
        print(f"Progress: {detector.confidence}%")