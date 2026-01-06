import cv2
import numpy as np
from datetime import datetime
import os


class DocumentScanner:
    def __init__(self):
        self.document_types = {
            '1': {'name': 'Zairyuu Card (在留カード)', 'sides': ['front', 'back']},
            '2': {'name': 'My Number Card (マイナンバーカード)', 'sides': ['front', 'back']},
            '3': {'name': 'Passport', 'sides': ['photo_page']},
            '4': {'name': 'Driver License', 'sides': ['front', 'back']}
        }

        # Create folders for captures
        os.makedirs('documents/zairyuu', exist_ok=True)
        os.makedirs('documents/mynumber', exist_ok=True)
        os.makedirs('documents/passport', exist_ok=True)
        os.makedirs('documents/driver_license', exist_ok=True)

        # Card detection parameters - balanced
        self.MIN_CARD_AREA = 30000  # Increased to avoid small objects
        self.MAX_CARD_AREA = 350000  # Reduced - typical card should be under this
        self.CARD_ASPECT_RATIO_MIN = 1.2  # ID cards typically 1.5-1.6
        self.CARD_ASPECT_RATIO_MAX = 2.0  # Allow some variation

    def order_points(self, pts):
        """Order points in clockwise order: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect

    def is_card_like(self, contour, frame_area):
        """Simplified validation - just check basics"""
        area = cv2.contourArea(contour)

        # Check size
        if area < self.MIN_CARD_AREA or area > self.MAX_CARD_AREA:
            return False, "area"

        # Check not too large relative to frame
        if area > frame_area * 0.75:
            return False, "too_large"

        # Must be 4 corners
        if len(contour) != 4:
            return False, "not_4_corners"

        # Check aspect ratio
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / float(h) if h > 0 else 0
        if not (self.CARD_ASPECT_RATIO_MIN <= aspect_ratio <= self.CARD_ASPECT_RATIO_MAX):
            return False, f"aspect_ratio_{aspect_ratio:.2f}"

        return True, "ok"

    def detect_card(self, frame, debug=False):
        """Detect rectangular card in frame - IMPROVED to ignore UI elements"""
        h, w = frame.shape[:2]
        frame_area = h * w

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Preprocessing
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # Use multiple detection methods
        # Method 1: Adaptive threshold
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        thresh_inv = cv2.bitwise_not(thresh)

        # Method 2: Canny edges with multiple thresholds
        edges1 = cv2.Canny(blurred, 20, 100)
        edges2 = cv2.Canny(blurred, 50, 150)

        # Combine methods
        combined = cv2.bitwise_or(edges1, edges2)
        combined = cv2.bitwise_or(combined, thresh_inv)

        # Morphological operations to connect edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        combined = cv2.dilate(combined, kernel, iterations=2)
        combined = cv2.erode(combined, kernel, iterations=1)

        # Find contours - try both RETR_EXTERNAL and RETR_LIST
        contours_ext, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_list, _ = cv2.findContours(combined, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # Combine and deduplicate
        all_contours = list(contours_ext) + list(contours_list)

        if debug:
            print(f"Found {len(all_contours)} total contours")

        candidates = []

        for idx, contour in enumerate(all_contours):
            area = cv2.contourArea(contour)

            # Skip if too small or too large
            if area < self.MIN_CARD_AREA:
                if debug and area > 5000:
                    print(f"Contour {idx}: area {area:.0f} too small (min: {self.MIN_CARD_AREA})")
                continue

            if area > self.MAX_CARD_AREA:
                if debug and area < frame_area * 0.9:  # Only print if not the whole frame
                    print(f"Contour {idx}: area {area:.0f} too large (max: {self.MAX_CARD_AREA})")
                continue

            # Check area relative to frame - card shouldn't be more than 50% of frame
            if area > frame_area * 0.5:
                if debug:
                    print(f"Contour {idx}: covers {100 * area / frame_area:.1f}% of frame (max 50%)")
                continue

            # Try to approximate as quadrilateral
            peri = cv2.arcLength(contour, True)

            best_approx = None
            for epsilon_mult in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]:
                approx = cv2.approxPolyDP(contour, epsilon_mult * peri, True)

                if len(approx) == 4:
                    best_approx = approx
                    break

            if best_approx is None:
                if debug:
                    print(f"Contour {idx}: couldn't approximate to 4 corners")
                continue

            # Check bounding box
            x, y, bw, bh = cv2.boundingRect(best_approx)

            # Skip if touching edges (likely the guide box)
            margin = 10
            if (x < margin or y < margin or
                    x + bw > w - margin or y + bh > h - margin):
                if debug:
                    print(f"Contour {idx}: touching frame edges (likely guide box)")
                continue

            aspect_ratio = bw / float(bh) if bh > 0 else 0

            # Check aspect ratio
            if not (self.CARD_ASPECT_RATIO_MIN <= aspect_ratio <= self.CARD_ASPECT_RATIO_MAX):
                if debug:
                    print(f"Contour {idx}: aspect {aspect_ratio:.2f} out of range "
                          f"({self.CARD_ASPECT_RATIO_MIN}-{self.CARD_ASPECT_RATIO_MAX})")
                continue

            # Calculate center distance
            center_x = x + bw / 2
            center_y = y + bh / 2
            frame_center_x = w / 2
            frame_center_y = h / 2
            distance_from_center = np.sqrt((center_x - frame_center_x) ** 2 +
                                           (center_y - frame_center_y) ** 2)

            if debug:
                print(f"✓ Contour {idx}: area={area:.0f}, aspect={aspect_ratio:.2f}, "
                      f"bbox=({x},{y},{bw},{bh})")

            candidates.append({
                'contour': best_approx,
                'box': (x, y, bw, bh),
                'area': area,
                'aspect_ratio': aspect_ratio,
                'distance_from_center': distance_from_center,
            })

        if not candidates:
            if debug:
                print("No valid candidates found")
            return None

        # Remove duplicates (contours that are very similar)
        unique_candidates = []
        for card in candidates:
            is_duplicate = False
            for existing in unique_candidates:
                # Check if areas are very similar (within 10%)
                area_diff = abs(card['area'] - existing['area']) / existing['area']
                if area_diff < 0.1:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_candidates.append(card)

        if debug and len(candidates) > len(unique_candidates):
            print(f"Removed {len(candidates) - len(unique_candidates)} duplicate candidates")

        # Score candidates - prefer larger and more centered
        for card in unique_candidates:
            size_score = card['area'] / self.MAX_CARD_AREA
            max_distance = np.sqrt((w / 2) ** 2 + (h / 2) ** 2)
            position_score = 1 - (card['distance_from_center'] / max_distance)
            card['score'] = 0.7 * size_score + 0.3 * position_score

        best_card = max(unique_candidates, key=lambda x: x['score'])

        if debug:
            print(f"Selected card: area={best_card['area']:.0f}, "
                  f"aspect={best_card['aspect_ratio']:.2f}, score={best_card['score']:.3f}")

        return best_card

    def check_card_quality(self, card_region):
        """Check if card image is clear enough AND has content"""
        if card_region.size == 0 or card_region.shape[0] < 50 or card_region.shape[1] < 50:
            return {'brightness': 0, 'sharpness': 0, 'has_content': False, 'is_good': False}

        gray = cv2.cvtColor(card_region, cv2.COLOR_BGR2GRAY)

        # Check brightness
        brightness = np.mean(gray)

        # Check blur (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Check if image has content/features (not just blank texture)
        # Use edge detection to check for meaningful content
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size

        # Check variance (blank/uniform regions have low variance)
        variance = np.var(gray)

        # A real card should have:
        # - Reasonable brightness (not too dark or too bright)
        # - Good sharpness
        # - Some edge density (text, photo, etc.)
        # - Reasonable variance (not uniform color)
        has_content = edge_density > 0.02 and variance > 200

        quality = {
            'brightness': brightness,
            'sharpness': laplacian_var,
            'edge_density': edge_density,
            'variance': variance,
            'has_content': has_content,
            'is_good': (brightness > 25 and
                        laplacian_var > 20 and
                        has_content)
        }

        return quality

    def draw_card_guide(self, frame, card_detected=False, quality=None, card_info=None):
        """Draw guide overlay for card placement"""
        h, w = frame.shape[:2]

        guide_w = int(w * 0.7)
        guide_h = int(guide_w / 1.586)

        center_x = w // 2
        center_y = h // 2

        x1 = center_x - guide_w // 2
        y1 = center_y - guide_h // 2
        x2 = center_x + guide_w // 2
        y2 = center_y + guide_h // 2

        # Color based on detection
        if card_detected and quality and quality['is_good']:
            color = (0, 255, 0)  # Green - ready to capture
            text = "READY - Press SPACE to capture"
            text_color = (0, 255, 0)
        elif card_detected:
            color = (0, 255, 255)  # Yellow - detected but not good quality
            text = "Card detected - Improve lighting or press 'C' to force"
            text_color = (0, 255, 255)
        else:
            color = (255, 255, 255)  # White - no card
            text = "Place card flat inside the frame"
            text_color = (255, 255, 255)

        # Draw guide box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

        # Draw corner markers
        corner_length = 30
        thickness = 4
        for (cx, cy) in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            dx = corner_length if cx == x1 else -corner_length
            dy = corner_length if cy == y1 else -corner_length
            cv2.line(frame, (cx, cy), (cx + dx, cy), color, thickness)
            cv2.line(frame, (cx, cy), (cx, cy + dy), color, thickness)

        # Draw instruction text
        cv2.putText(frame, text, (center_x - 350, y1 - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

        # Draw quality indicators
        if quality:
            y_offset = y2 + 40
            brightness_status = f"Brightness: {quality['brightness']:.0f} {'✓' if quality['brightness'] > 25 else '✗'}"
            sharpness_status = f"Sharpness: {quality['sharpness']:.0f} {'✓' if quality['sharpness'] > 20 else '✗'}"
            content_status = f"Content: {'✓' if quality.get('has_content', False) else '✗ no card features'}"

            b_color = (0, 255, 0) if quality['brightness'] > 25 else (0, 0, 255)
            s_color = (0, 255, 0) if quality['sharpness'] > 20 else (0, 0, 255)
            c_color = (0, 255, 0) if quality.get('has_content', False) else (0, 0, 255)

            cv2.putText(frame, brightness_status, (x1, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, b_color, 2)
            cv2.putText(frame, sharpness_status, (x1, y_offset + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, s_color, 2)
            cv2.putText(frame, content_status, (x1, y_offset + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, c_color, 2)

        # Draw card info if detected
        if card_info:
            info_y = 30
            cv2.putText(frame, f"Area: {card_info['area']:,}", (10, info_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, f"Aspect: {card_info.get('aspect_ratio', 0):.2f}", (10, info_y + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Draw controls at bottom
        cv2.putText(frame, "SPACE: Auto Capture | C: Force Capture | Q: Quit", (20, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return frame

    def perspective_transform(self, image, card_contour):
        """Apply perspective transform to get flat card image"""
        pts = card_contour.reshape(4, 2)
        rect = self.order_points(pts)

        (tl, tr, br, bl) = rect

        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        return warped

    def scan_document(self, doc_type, side_name):
        """Scan a single side of document"""
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Cannot open camera")
            return None

        print(f"\n📸 Scanning: {doc_type} - {side_name}")
        print("Position the card FLAT and CENTERED in the frame")
        print("Press SPACE when GREEN (auto quality check)")
        print("Press 'C' to FORCE capture (ignore quality)")
        print("Press 'D' to toggle DEBUG mode")
        print("Press 'Q' to quit\n")

        captured_image = None
        quit_flag = False
        debug_mode = False

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            display_frame = frame.copy()

            # Detect card
            card = self.detect_card(frame, debug=debug_mode)

            if card:
                # Draw detected card outline (thicker for visibility)
                cv2.drawContours(display_frame, [card['contour']], -1, (0, 255, 0), 4)

                # Get card region for quality check
                x, y, w, h = card['box']
                # Add small padding to avoid edge artifacts
                padding = 5
                y1 = max(0, y - padding)
                y2 = min(frame.shape[0], y + h + padding)
                x1 = max(0, x - padding)
                x2 = min(frame.shape[1], x + w + padding)
                card_region = frame[y1:y2, x1:x2]

                quality = self.check_card_quality(card_region)

                # Draw guide with detection status
                display_frame = self.draw_card_guide(display_frame, True, quality, card)
            else:
                quality = None
                display_frame = self.draw_card_guide(display_frame, False, None, None)

            cv2.imshow('Document Scanner', display_frame)

            key = cv2.waitKey(1) & 0xFF

            # Toggle debug mode on 'D'
            if key == ord('d') or key == ord('D'):
                debug_mode = not debug_mode
                print(f"🐛 Debug mode: {'ON' if debug_mode else 'OFF'}")

            # Auto capture on SPACE (quality check)
            if key == ord(' '):
                if card and quality and quality['is_good']:
                    warped = self.perspective_transform(frame, card['contour'])
                    captured_image = warped

                    print("✓ Document captured (auto)!")

                    # Show preview
                    h, w = warped.shape[:2]
                    aspect = w / h
                    preview_w = 800
                    preview_h = int(preview_w / aspect)
                    preview = cv2.resize(warped, (preview_w, preview_h))
                    cv2.imshow('Captured Document - Check quality (window closes in 3s)', preview)
                    cv2.waitKey(3000)
                    cv2.destroyWindow('Captured Document - Check quality (window closes in 3s)')
                    break
                else:
                    print("⚠️ Card not ready - improve lighting or hold steadier")

            # FORCE capture on 'C' (ignore quality)
            if key == ord('c') or key == ord('C'):
                if card:
                    warped = self.perspective_transform(frame, card['contour'])
                    captured_image = warped

                    print("✓ Document captured (forced)!")

                    # Show preview
                    h, w = warped.shape[:2]
                    aspect = w / h
                    preview_w = 800
                    preview_h = int(preview_w / aspect)
                    preview = cv2.resize(warped, (preview_w, preview_h))
                    cv2.imshow('Captured Document - Check quality (window closes in 3s)', preview)
                    cv2.waitKey(3000)
                    cv2.destroyWindow('Captured Document - Check quality (window closes in 3s)')
                    break
                else:
                    print("⚠️ No card detected - position card in frame")

            # Quit on 'q' or 'Q'
            if key == ord('q') or key == ord('Q'):
                print("🛑 Quitting...")
                quit_flag = True
                break

        cap.release()
        cv2.destroyAllWindows()

        if quit_flag:
            return "QUIT"
        return captured_image

    def run(self):
        """Main document scanning workflow"""
        print("=" * 60)
        print("📄 eKYC DOCUMENT SCANNER")
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
            return {}

        if choice not in self.document_types:
            print("❌ Invalid choice")
            return {}

        doc_info = self.document_types[choice]
        doc_name = doc_info['name']
        sides = doc_info['sides']

        print(f"\n✓ Selected: {doc_name}")
        print(f"📋 Need to scan {len(sides)} side(s)")
        print("💡 Press 'Q' anytime to quit, or Ctrl+C at the prompt\n")

        captures = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for side in sides:
            print(f"\n--- Scanning {side} ---")

            try:
                input(f"Press ENTER to start scanning {side} (or Ctrl+C to quit)...")
            except KeyboardInterrupt:
                print("\n🛑 Scan cancelled by user (Ctrl+C)")
                return captures

            image = self.scan_document(doc_name, side)

            # Check if user quit
            if isinstance(image, str) and image == "QUIT":
                print("\n🛑 Scan cancelled by user")
                return captures

            if image is not None:
                # Save captured image
                if 'Zairyuu' in doc_name:
                    folder = 'zairyuu'
                elif 'My Number' in doc_name:
                    folder = 'mynumber'
                elif 'Passport' in doc_name:
                    folder = 'passport'
                elif 'Driver' in doc_name:
                    folder = 'driver_license'
                else:
                    folder = 'other'

                filename = f"documents/{folder}/{side}_{timestamp}.jpg"
                cv2.imwrite(filename, image)

                captures[side] = {
                    'image': image,
                    'filename': filename
                }

                print(f"✓ Saved: {filename}")
            else:
                print(f"✗ Failed to capture {side}")

        print("\n" + "=" * 60)
        print(f"✓ Document scan complete!")
        print(f"✓ Captured {len(captures)}/{len(sides)} sides")
        print("=" * 60)

        return captures


if __name__ == "__main__":
    scanner = DocumentScanner()

    try:
        results = scanner.run()

        if results:
            print("\n✓ Ready for OCR processing!")
        else:
            print("\n✗ No documents captured")
    except KeyboardInterrupt:
        print("\n\n🛑 Program terminated by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()