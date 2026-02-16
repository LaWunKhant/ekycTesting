import os
from typing import Dict, List

import cv2
import numpy as np


def _safe_float(value: float) -> float:
    return float(round(float(value), 4))


def _analyze_single_frame(path: str) -> Dict[str, float]:
    img = cv2.imread(path)
    if img is None:
        return {
            "ok": 0.0,
            "edge_strength": 0.0,
            "angle": 0.0,
            "area_ratio": 0.0,
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 75, 180)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {
            "ok": 0.0,
            "edge_strength": 0.0,
            "angle": 0.0,
            "area_ratio": 0.0,
        }

    h, w = gray.shape
    frame_area = float(max(h * w, 1))

    candidate = max(contours, key=cv2.contourArea)
    contour_area = float(cv2.contourArea(candidate))
    if contour_area <= 0:
        return {
            "ok": 0.0,
            "edge_strength": 0.0,
            "angle": 0.0,
            "area_ratio": 0.0,
        }

    rect = cv2.minAreaRect(candidate)
    angle = float(rect[2])

    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [candidate], -1, 255, thickness=2)
    edge_strength = float(np.mean(edges[mask > 0])) / 255.0

    area_ratio = contour_area / frame_area

    return {
        "ok": 1.0,
        "edge_strength": edge_strength,
        "angle": angle,
        "area_ratio": area_ratio,
    }


def analyze_card_physicality(image_paths: List[str]) -> Dict[str, float]:
    existing_paths = [p for p in image_paths if p and os.path.exists(p)]
    if len(existing_paths) < 2:
        return {
            "verified": False,
            "physical_card_score": 0.0,
            "edge_consistency_score": 0.0,
            "depth_variation_score": 0.0,
            "frames_used": len(existing_paths),
            "reason": "not_enough_frames",
        }

    metrics = [_analyze_single_frame(path) for path in existing_paths]
    valid = [m for m in metrics if m["ok"] > 0]
    if len(valid) < 2:
        return {
            "verified": False,
            "physical_card_score": 0.0,
            "edge_consistency_score": 0.0,
            "depth_variation_score": 0.0,
            "frames_used": len(valid),
            "reason": "card_not_detected",
        }

    edge_vals = np.array([m["edge_strength"] for m in valid], dtype=np.float32)
    area_vals = np.array([m["area_ratio"] for m in valid], dtype=np.float32)
    angle_vals = np.array([m["angle"] for m in valid], dtype=np.float32)

    edge_consistency = float(np.clip(np.mean(edge_vals), 0.0, 1.0))

    # Physical cards typically show perspective/depth changes when tilted.
    area_spread = float(np.ptp(area_vals))
    angle_spread = float(np.ptp(angle_vals))
    depth_variation = float(np.clip((area_spread * 8.0) + (angle_spread / 60.0), 0.0, 1.0))

    score = float(np.clip((0.55 * edge_consistency) + (0.45 * depth_variation), 0.0, 1.0))
    verified = score >= 0.45

    return {
        "verified": bool(verified),
        "physical_card_score": _safe_float(score * 100.0),
        "edge_consistency_score": _safe_float(edge_consistency * 100.0),
        "depth_variation_score": _safe_float(depth_variation * 100.0),
        "frames_used": len(valid),
        "area_spread": _safe_float(area_spread),
        "angle_spread": _safe_float(angle_spread),
        "reason": "ok",
    }
