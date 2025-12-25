import cv2
import numpy as np
import dlib
from scipy.spatial import distance as dist
import time
import os
import urllib.request
import bz2


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


class MouthDetectionLiveness:
    def __init__(self):
        self.detector = dlib.get_frontal_face_detector()
        predictor_path = download_shape_predictor()
        self.predictor = dlib.shape_predictor(predictor_path)

        # Mouth landmarks (inner mouth)
        self.MOUTH_OUTER = list(range(48, 60))
        self.MOUTH_INNER = list(range(60, 68))

        # Mouth opening detection
        self.MOUTH_AR_THRESH = 0.5  # Mouth aspect ratio threshold
        self.mouth_open_frames = 0
        self.mouth_closed_frames = 0
        self.mouth_open_counter = 0
        self.mouth_is_open = False

        self.challenges = {
            'center': {'completed': False, 'name': 'Face the camera', 'frames': 0},
            'left': {'completed': False, 'name': 'Turn head LEFT', 'frames': 0},
            'right': {'completed': False, 'name': 'Turn head RIGHT', 'frames': 0},
            'mouth': {'completed': False, 'name': 'Open mouth 2 times', 'frames': 0}
        }

        self.REQUIRED_MOUTH_OPENS = 2

    def mouth_aspect_ratio(self, mouth):
        """Calculate mouth aspect ratio (MAR)"""
        # Mouth landmarks for outer mouth (12 points: 48-59)
        # Vertical distances (top lip to bottom lip)
        A = dist.euclidean(mouth[2], mouth[10])  # Upper center to lower center
        B = dist.euclidean(mouth[3], mouth[9])  # Left inner
        C = dist.euclidean(mouth[4], mouth[8])  # Right inner

        # Horizontal distance (mouth width)
        D = dist.euclidean(mouth[0], mouth[6])  # Left corner to right corner

        # Avoid division by zero
        if D == 0:
            return 0

        # MAR formula
        mar = (A + B + C) / (3.0 * D)
        return mar

    def get_landmarks(self, gray, rect):
        shape = self.predictor(gray, rect)
        coords = np.zeros((68, 2), dtype=int)
        for i in range(68):
            coords[i] = (shape.part(i).x, shape.part(i).y)
        return coords

    def detect_head_position(self, landmarks, frame_width):
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

        if width_ratio < 0.80 or offset < -30:
            return 'left'
        elif width_ratio > 1.25 or offset > 30:
            return 'right'
        else:
            return 'center'

    def get_progress(self):
        completed = sum(1 for c in self.challenges.values() if c['completed'])
        return int((completed / len(self.challenges)) * 100)

    def draw_mouth_region(self, frame, mouth_coords):
        """Draw mouth outline for visual feedback"""
        # Draw outer mouth
        for i in range(len(mouth_coords)):
            cv2.line(frame,
                     tuple(mouth_coords[i]),
                     tuple(mouth_coords[(i + 1) % len(mouth_coords)]),
                     (0, 255, 255), 2)

    def detect_mouth_opening(self, mar):
        """Detect mouth opening with state machine"""
        if self.challenges['mouth']['completed']:
            return False

        # Mouth is open
        if mar > self.MOUTH_AR_THRESH:
            self.mouth_open_frames += 1
            self.mouth_closed_frames = 0

            # Confirm mouth is open (3 consecutive frames)
            if self.mouth_open_frames >= 3 and not self.mouth_is_open:
                self.mouth_is_open = True
                print(f"👄 Mouth opened!")
        # Mouth is closed
        else:
            self.mouth_closed_frames += 1

            # If mouth was open and now closed, count it
            if self.mouth_is_open and self.mouth_closed_frames >= 3:
                self.mouth_open_counter += 1
                self.mouth_is_open = False
                self.mouth_open_frames = 0
                print(f"✓ Mouth close detected! Count: {self.mouth_open_counter}/{self.REQUIRED_MOUTH_OPENS}")
                return True

            if not self.mouth_is_open:
                self.mouth_open_frames = 0

        return False

    def draw_direction_guides(self, frame, current_position):
        h, w = frame.shape[:2]

        if not self.challenges['left']['completed']:
            color = (0, 255, 255) if current_position == 'left' else (80, 80, 80)
            thickness = 8 if current_position == 'left' else 4
            cv2.arrowedLine(frame, (150, h // 2), (50, h // 2), color, thickness, tipLength=0.5)
            cv2.putText(frame, 'LEFT', (60, h // 2 + 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        if not self.challenges['right']['completed']:
            color = (0, 255, 255) if current_position == 'right' else (80, 80, 80)
            thickness = 8 if current_position == 'right' else 4
            cv2.arrowedLine(frame, (w - 150, h // 2), (w - 50, h // 2), color, thickness, tipLength=0.5)
            cv2.putText(frame, 'RIGHT', (w - 160, h // 2 + 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        if not self.challenges['center']['completed']:
            color = (0, 255, 0) if current_position == 'center' else (80, 80, 80)
            thickness = 6 if current_position == 'center' else 2
            cv2.circle(frame, (w // 2, h // 2), 30, color, thickness)

    def draw_ui(self, frame, mar):
        h, w = frame.shape[:2]

        # Progress bar
        cv2.rectangle(frame, (20, 20), (w - 20, 70), (30, 30, 30), -1)
        progress = self.get_progress()
        bar_width = int((w - 50) * (progress / 100))
        cv2.rectangle(frame, (25, 25), (25 + bar_width, 65), (0, 255, 0), -1)
        cv2.putText(frame, f'Progress: {progress}%', (w // 2 - 80, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Mouth status
        if not self.challenges['mouth']['completed']:
            if mar > self.MOUTH_AR_THRESH:
                mouth_status = "OPEN"
                mouth_color = (0, 255, 0)
            else:
                mouth_status = "CLOSED"
                mouth_color = (200, 200, 200)

            cv2.putText(frame, f'Mouth: {mouth_status}',
                        (20, h - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mouth_color, 2)
            cv2.putText(frame, f'MAR: {mar:.2f} (Threshold: {self.MOUTH_AR_THRESH:.2f})',
                        (20, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            cv2.putText(frame, f'Opens: {self.mouth_open_counter}/{self.REQUIRED_MOUTH_OPENS}',
                        (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # Checklist
        y_offset = 100
        for key, challenge in self.challenges.items():
            if challenge['completed']:
                status = '✓'
                color = (0, 255, 0)
            elif challenge['frames'] > 3:
                status = '⋯'
                color = (0, 255, 255)
            else:
                status = '○'
                color = (150, 150, 150)

            text = f"{status} {challenge['name']}"
            cv2.putText(frame, text, (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            y_offset += 35

        # Current instruction
        if progress < 100:
            current = next((c['name'] for c in self.challenges.values()
                            if not c['completed']), None)
            if current:
                pulse = int(abs(np.sin(time.time() * 4) * 55) + 200)
                cv2.putText(frame, f">>> {current} <<<", (w // 2 - 200, h - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (pulse, 255, pulse), 3)
        else:
            cv2.putText(frame, "✓ COMPLETE!", (w // 2 - 120, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 3)

    def run(self):
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Cannot open camera")
            return False

        print("🎥 eKYC Liveness - MOUTH DETECTION")
        print("👄 Open your mouth naturally 2 times")
        print("⚡ This is more reliable than blink detection!\n")

        start_time = time.time()

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
                rect = rects[0]
                landmarks = self.get_landmarks(gray, rect)

                x, y = rect.left(), rect.top()
                w_face, h_face = rect.right() - x, rect.bottom() - y
                cv2.rectangle(frame, (x, y), (x + w_face, y + h_face), (0, 255, 0), 2)

                # Get mouth landmarks
                mouth = landmarks[self.MOUTH_OUTER]

                # Calculate mouth aspect ratio
                mar = self.mouth_aspect_ratio(mouth)

                # Draw mouth region
                self.draw_mouth_region(frame, mouth)

                # Detect mouth opening
                if self.detect_mouth_opening(mar):
                    if self.mouth_open_counter >= self.REQUIRED_MOUTH_OPENS:
                        self.challenges['mouth']['completed'] = True
                        print("✓ Mouth challenge completed!")

                # Head position
                position = self.detect_head_position(landmarks, w)
                current_position = position

                for pos in ['center', 'left', 'right']:
                    if position == pos:
                        self.challenges[pos]['frames'] += 1
                        if self.challenges[pos]['frames'] >= 10 and not self.challenges[pos]['completed']:
                            self.challenges[pos]['completed'] = True
                            print(f"✓ {pos.capitalize()} confirmed!")
                    else:
                        self.challenges[pos]['frames'] = max(0, self.challenges[pos]['frames'] - 3)

                cv2.putText(frame, f'Head: {position.upper()}', (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                self.draw_ui(frame, mar)

            self.draw_direction_guides(frame, current_position)

            if self.get_progress() == 100:
                elapsed = time.time() - start_time
                print(f"\n✓✓✓ VERIFIED in {elapsed:.1f}s")
                cv2.imshow('eKYC Liveness Verification', frame)
                cv2.waitKey(2000)
                break

            cv2.imshow('eKYC Liveness Verification', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        return self.get_progress() == 100


if __name__ == "__main__":
    detector = MouthDetectionLiveness()
    success = detector.run()

    if success:
        print("✓ LIVE user verified")
        print("✓ Ready for document scanning!")
    else:
        print("✗ Verification incomplete")