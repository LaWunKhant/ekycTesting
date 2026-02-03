🌙 MoonKYC – eKYC Identity Verification System (Prototype)

MoonKYC is a full-stack eKYC (Electronic Know Your Customer) prototype that simulates real-world identity verification systems used by banks, fintech, and crypto platforms.
It combines document capture, liveness detection, and multi-model face verification into a single secure pipeline.

🔍 Features

📸 ID Card Capture (Front & Back)

🤳 Live Selfie Capture

🎭 Web-based Liveness Detection

Head turn (Left / Right)

Mouth open challenge

Face presence verification

🧠 Face Extraction from ID

🔬 Multi-model Face Comparison:

ArcFace

FaceNet

VGG-Face

📊 Ensemble Similarity Scoring

✅ Final Verification Decision System

🌍 Public Testing via Ngrok Tunnel

(System Flow)
User
  ↓
Capture ID → Capture Selfie → Liveness Check
  ↓
Extract Face from ID
  ↓
Run 3 AI Face Models
  ↓
Combine Scores + Liveness Boost
  ↓
Verification Decision

(🔐 Security Design)

Prevents spoof attacks using live facial actions

Multi-model voting system reduces false acceptance

Confidence threshold system

Audit-friendly logs and structured outputs

📈 Sample Output
{
  "average_similarity": 54.0,
  "final_confidence": 64.0,
  "liveness": "verified",
  "decision": "VERIFIED"
}

🚀 How to Run
git clone https://github.com/yourname/moonkyc
cd moonkyc
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m kyc.moonkyc_server
ngrok http 3000

⚠️ Disclaimer

This project is a research and educational prototype, not production-ready.
Do not use real identity documents in public environments.
