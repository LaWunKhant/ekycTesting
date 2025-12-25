import cv2
import os
from datetime import datetime

def ekyc_instruction():
    print("""
    📋 VERIFICATION INSTRUCTIONS:
    1. Remove glasses, hats, masks
    2. Face the camera directly
    3. Ensure good lighting
    4. Keep neutral expression
    """)

# Create folder to save captured faces
if not os.path.exists('captured_faces'):
    os.makedirs('captured_faces')

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Cannot open camera")
    exit()

print("Camera opened successfully!")
print("Press 'SPACE' to capture face")
print("Press 'q' to quit")

capture_count = 0

while True:
    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame. Exiting...")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.2,
        minNeighbors=7,
        minSize=(60, 60),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    # Draw rectangle
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
        cv2.putText(frame, 'Face Ready', (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    # Instructions
    cv2.putText(frame, f'Faces: {len(faces)} | Captured: {capture_count}', (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, 'SPACE: Capture | Q: Quit', (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow('Face Capture System', frame)

    key = cv2.waitKey(1) & 0xFF

    # Press SPACE to capture
    if key == ord(' '):
        if len(faces) == 1:
            # Save the captured face
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'captured_faces/face_{timestamp}.jpg'

            # Save full frame
            cv2.imwrite(filename, frame)

            # Also save just the face region
            x, y, w, h = faces[0]
            face_only = frame[y:y + h, x:x + w]
            face_filename = f'captured_faces/face_only_{timestamp}.jpg'
            cv2.imwrite(face_filename, face_only)

            capture_count += 1
            print(f"✓ Captured! Saved as {filename}")

            # Visual feedback
            cv2.putText(frame, 'CAPTURED!', (200, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
            cv2.imshow('Face Capture System', frame)
            cv2.waitKey(500)  # Show "CAPTURED!" for 0.5 seconds
        else:
            print(f"✗ Detection issue: Found {len(faces)} faces. Need exactly 1 face.")

    # Press 'q' to quit
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print(f"\nTotal faces captured: {capture_count}")
print("Camera closed!")