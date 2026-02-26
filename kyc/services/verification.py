from dataclasses import dataclass
from typing import Any, Dict, List

from deepface import DeepFace


@dataclass
class VerificationConfig:
    # similarity thresholds (0-100, higher is better)
    min_similarity: Dict[str, float] = None
    require_arcface: bool = True
    arcface_min: float = 60.0
    max_range: float = 40.0  # disagreement cutoff

    def __post_init__(self):
        if self.min_similarity is None:
            self.min_similarity = {
                "VGG-Face": 65.0,
                "Facenet": 70.0,
                "ArcFace": 60.0,
            }


class FaceVerificationService:
    def __init__(self, config: VerificationConfig):
        self.cfg = config
        self.models = list(self.cfg.min_similarity.keys())

    def verify(self, id_face_path: str, selfie_path: str) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []

        for model in self.models:
            r = DeepFace.verify(
                img1_path=id_face_path,
                img2_path=selfie_path,
                model_name=model,
                distance_metric="cosine",
                enforce_detection=False,
            )

            distance = float(r["distance"])
            similarity = (1.0 - distance) * 100.0

            passed = similarity >= self.cfg.min_similarity[model]

            results.append(
                {
                    "model": model,
                    "distance": distance,
                    "similarity": similarity,
                    "passed": passed,
                }
            )

        sims = [x["similarity"] for x in results]
        avg_similarity = sum(sims) / len(sims)
        sim_range = max(sims) - min(sims)

        # Disagreement safety
        if sim_range > self.cfg.max_range:
            return {
                "verified": False,
                "reason": f"model_disagreement_range_{sim_range:.1f}",
                "avg_similarity": avg_similarity,
                "range": sim_range,
                "models": results,
            }

        # Require ArcFace pass (recommended)
        if self.cfg.require_arcface:
            arc = next(x for x in results if x["model"] == "ArcFace")
            if arc["similarity"] < self.cfg.arcface_min:
                return {
                    "verified": False,
                    "reason": "arcface_below_min",
                    "avg_similarity": avg_similarity,
                    "range": sim_range,
                    "models": results,
                }

        # Ensemble pass rule: majority pass
        passes = sum(1 for x in results if x["passed"])
        verified = passes >= 2

        return {
            "verified": verified,
            "reason": "ok" if verified else "insufficient_model_passes",
            "avg_similarity": avg_similarity,
            "range": sim_range,
            "models": results,
        }
