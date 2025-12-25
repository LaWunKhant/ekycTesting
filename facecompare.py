from deepface import DeepFace


def compare_faces_robust(image1_path, image2_path):
    """Compare using multiple models for better accuracy"""

    models = ["Facenet", "VGG-Face", "ArcFace"]
    results = []

    print(f"\n{'=' * 60}")
    print(f"Image 1: {image1_path}")
    print(f"Image 2: {image2_path}")
    print(f"{'=' * 60}\n")

    for model in models:
        try:
            result = DeepFace.verify(
                img1_path=image1_path,
                img2_path=image2_path,
                model_name=model,
                enforce_detection=True
            )

            distance = result['distance']
            similarity = (1 - distance) * 100
            verified = result['verified']

            results.append({
                'model': model,
                'distance': distance,
                'similarity': similarity,
                'verified': verified
            })

            print(
                f"{model:15} | Distance: {distance:.3f} | Similarity: {similarity:5.1f}% | {'✓ YES' if verified else '✗ NO'}")

        except Exception as e:
            print(f"{model:15} | Error: {e}")

    # Average decision
    if results:
        avg_similarity = sum(r['similarity'] for r in results) / len(results)
        votes_yes = sum(1 for r in results if r['verified'])
        final_match = votes_yes >= 2  # Majority vote

        print(f"\n{'-' * 60}")
        print(f"Average Similarity: {avg_similarity:.1f}%")
        print(f"Votes: {votes_yes}/{len(results)} models say YES")
        print(f"Final Decision: {'✓ MATCH' if final_match else '✗ NO MATCH'}")
        print(f"{'=' * 60}\n")

        return final_match

    return False


# Test with your glasses vs no-glasses images
if __name__ == "__main__":
    image1 = "captured_faces/face_only_20251225_115558.jpg"  # without glasses
    image2 = "captured_faces/face_only_20251225_121656.jpg"  # with glasses

    print("Testing ROBUST face comparison...")
    compare_faces_robust(image1, image2)