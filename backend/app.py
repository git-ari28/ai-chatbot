from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import os
from io import BytesIO
import requests
import fitz

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Content-Type", "x-api-key"],
    methods=["GET", "POST", "OPTIONS"]
)

OLLAMA_URL = "http://ai-chatbot-ollama-1:11434/api/generate"
API_KEY = "teacher123"

stored_chunks = []

# ---------------- AUTH ----------------
def check_auth(req):
    return req.headers.get("x-api-key") == API_KEY

# ---------------- PDF → CHUNKS ----------------
def extract_chunks(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""

    for page in doc:
        text += page.get_text()

    clean = " ".join(text.split())

    # safer filtering
    sentences = clean.split(".")
    filtered = [s.strip() for s in sentences if len(s.strip()) > 30]

    if not filtered:
        filtered = [clean]

    clean_text = ". ".join(filtered)

    # small chunks (IMPORTANT for phi3)
    chunks = [clean_text[i:i+250] for i in range(0, len(clean_text), 250)]

    print("📦 CHUNKS:", len(chunks))

    return chunks[:3]   # 🔥 LIMIT (important)

# ---------------- OLLAMA ----------------
def generate(prompt):
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": "phi3:mini",   # ✅ BACK TO PHI3
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        data = res.json()
        print("🤖 RESPONSE:", data)

        return data.get("response", "")

    except Exception as e:
        print("❌ ERROR:", e)
        return ""

# ---------------- CLEAN OUTPUT ----------------
def clean_output(text):
    lines = text.split("\n")
    good = []

    for line in lines:
        if any(x in line.lower() for x in ["text:", "example", "generate", "format"]):
            continue
        good.append(line.strip())

    return "\n".join(good)

# ---------------- ROUTES ----------------

@app.route("/upload", methods=["POST"])
def upload():
    global stored_chunks

    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400

    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", file.filename)
    file.save(path)

    stored_chunks = extract_chunks(path)

    if not stored_chunks:
        return jsonify({"error": "Processing failed"}), 500

    return jsonify({"message": "PDF ready"})

@app.route("/generate_questions", methods=["POST"])
def generate_questions():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    if not stored_chunks:
        return jsonify({"error": "Upload PDF first"}), 400

    outputs = []

    for chunk in stored_chunks:
        prompt = f"""
Generate EXACTLY:

5 MCQs (each with 4 options + correct answer)
2 short answer questions with answers

STRICT RULES:
- No explanations
- No instructions
- No repeating text
- Only questions

FORMAT:

Q1:
A.
B.
C.
D.
Answer:

Q2:
...

Short 1:
Question:
Answer:

Text:
{chunk}
"""

        result = generate(prompt)
        cleaned = clean_output(result)

        if cleaned:
            outputs.append(cleaned)

    final = "\n\n".join(outputs)

    return jsonify({
        "mcqs": final,
        "short_questions": final,
        "answers": final
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)