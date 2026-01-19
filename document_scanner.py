import cv2
import numpy as np
from datetime import datetime
import os


class SimpleDocumentScanner:
    def __init__(self):
        self.document_types = {
            '1': {'name': 'Zairyuu Card', 'sides': ['front', 'back']},
            '2': {'name': 'My Number Card', 'sides': ['front', 'back']},
            '3': {'name': 'Passport', 'sides': ['photo_page']},
            '4': {'name': 'Driver License', 'sides': ['front', 'back']}
        }

        # Create folders
        os.makedirs('documents/zairyuu', exist_ok=True)
        os.makedirs('documents/mynumber', exist_ok=True)
        os.makedirs('documents/passport', exist_ok=True)
        os.makedirs('documents/driver_license', exist_ok=True)
        os.makedirs('documents/selfies', exist_ok=True)

    def simple_capture(self, instruction_text, auto_continue=True):
        """Simple point-and-shoot capture - auto continues after capture"""
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Cannot open camera")
            return None

        print(f"\n📸 {instruction_text}")
        print("Press SPACE to capture")
        print("Press 'Q' to quit\n")

        captured_image = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            display_frame = frame.copy()
            h, w = display_frame.shape[:2]

            # Simple overlay - just instructions
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)

            # Instructions
            cv2.putText(display_frame, instruction_text, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.putText(display_frame, "Press SPACE to capture | Q to quit", (20, 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            # Simple center guide
            center_x, center_y = w // 2, h // 2
            cv2.circle(display_frame, (center_x, center_y), 10, (0, 255, 0), 2)
            cv2.line(display_frame, (center_x - 20, center_y), (center_x + 20, center_y), (0, 255, 0), 2)
            cv2.line(display_frame, (center_x, center_y - 20), (center_x, center_y + 20), (0, 255, 0), 2)

            cv2.imshow('Simple Document Scanner', display_frame)

            key = cv2.waitKey(1) & 0xFF

            # Capture on SPACE
            if key == ord(' '):
                captured_image = frame.copy()
                print("✓ Captured!")

                # Show preview for 1.5 seconds
                preview = cv2.resize(frame, (800, 600))
                cv2.imshow('Captured - Auto-continuing...', preview)
                cv2.waitKey(1500)  # Show for 1.5 seconds
                cv2.destroyWindow('Captured - Auto-continuing...')

                # Auto-continue (no need to press ENTER)
                break

            # Quit on Q
            if key == ord('q') or key == ord('Q'):
                print("🛑 Cancelled")
                cap.release()
                cv2.destroyAllWindows()
                return None

        cap.release()
        cv2.destroyAllWindows()

        return captured_image

    def run(self):
        """Simple workflow - auto continues after each capture"""
        print("=" * 60)
        print("📄 SIMPLE eKYC DOCUMENT SCANNER")
        print("=" * 60)
        print("\nPlease choose document type:")
        print("1. Zairyuu Card (在留カード)")
        print("2. My Number Card (マイナンバーカード)")
        print("3. Passport")
        print("4. Driver License")
        print("5. Quit")
        print("\nEnter choice (1-5): ", end="")

        choice = input().strip()

        if choice == '5':
            print("👋 Goodbye!")
            return None

        if choice not in self.document_types:
            print("❌ Invalid choice")
            return None

        doc_info = self.document_types[choice]
        doc_name = doc_info['name']
        sides = doc_info['sides']

        print(f"\n✓ Selected: {doc_name}")
        print(f"📋 Will capture {len(sides)} side(s) + selfie")
        print("💡 Camera will open automatically for each capture\n")

        import time
        time.sleep(2)  # Give user 2 seconds to read

        captures = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Map document names to folder names
        folder_map = {
            'Zairyuu Card': 'zairyuu',
            'My Number Card': 'mynumber',
            'Passport': 'passport',
            'Driver License': 'driver_license'
        }

        folder = folder_map.get(doc_name, 'unknown')

        # Capture each side - NO MANUAL ENTER NEEDED
        for i, side in enumerate(sides, 1):
            print(f"\n{'=' * 60}")
            print(f"📸 CAPTURE {i}/{len(sides) + 1}: {side.upper()}")
            print(f"{'=' * 60}")
            print("Get ready... camera opening in 2 seconds...")
            time.sleep(2)

            instruction = f"Show {side} of {doc_name}"
            image = self.simple_capture(instruction)

            if image is None:
                print(f"✗ Cancelled")
                return None

            # Save image
            filename = f"documents/{folder}/{side}_{timestamp}.jpg"
            cv2.imwrite(filename, image)

            captures[side] = {
                'image': image,
                'filename': filename
            }

            print(f"✓ Saved: {filename}")
            print("✓ Auto-continuing to next capture...")

        # Capture selfie - NO MANUAL ENTER NEEDED
        print(f"\n{'=' * 60}")
        print(f"📸 CAPTURE {len(sides) + 1}/{len(sides) + 1}: SELFIE")
        print(f"{'=' * 60}")
        print("Get ready for selfie... camera opening in 2 seconds...")
        time.sleep(2)

        instruction = "Take your selfie (face clearly visible)"
        selfie = self.simple_capture(instruction)

        if selfie is None:
            print("✗ Selfie cancelled")
            return captures

        # Save selfie
        selfie_filename = f"documents/selfies/selfie_{timestamp}.jpg"
        cv2.imwrite(selfie_filename, selfie)

        captures['selfie'] = {
            'image': selfie,
            'filename': selfie_filename
        }

        print(f"✓ Saved: {selfie_filename}")

        print("\n" + "=" * 60)
        print(f"✓ All captures complete!")
        print(f"✓ Document sides: {len(sides)}")
        print(f"✓ Selfie: ✓")
        print("=" * 60)

        return captures


if __name__ == "__main__":
    scanner = SimpleDocumentScanner()
    results = scanner.run()

    if results:
        print("\n✅ Ready for:")
        print("   1. OCR text extraction (Tesseract/EasyOCR)")
        print("   2. Face extraction from ID")
        print("   3. Face comparison with selfie")
    else:
        print("\n✗ No documents captured")