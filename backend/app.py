from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import os
from io import BytesIO
import requests
import fitz  # PyMuPDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

app = Flask(__name__)

# ✅ CORS FIX
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

    # clean text
    clean = " ".join(text.split())

    # split into chunks (300 chars)
    chunks = [clean[i:i+300] for i in range(0, len(clean), 300)]

    return chunks[:5]   # ✅ limit for performance

# ---------------- OLLAMA ----------------
def generate(prompt):
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": "tinyllama",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        data = res.json()
        return data.get("response", "")

    except Exception as e:
        print("❌ Ollama error:", e)
        return ""

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

    return jsonify({"message": "PDF uploaded and processed"})

@app.route("/generate_questions", methods=["POST"])
def generate_questions():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    if not stored_chunks:
        return jsonify({"error": "Upload PDF first"}), 400

    print("🔥 Generating from chunks...")

    mcqs = []
    shorts = []

    # generate per chunk
    for chunk in stored_chunks:
        prompt = f"""
You are a strict exam generator.

Generate:
- 1 MCQ with answer
- 1 short question with answer

Format:
Q:
A)
B)
C)
D)
Answer:

Short:
Question:
Answer:

Text:
{chunk}
"""
        result = generate(prompt)

        if result:
            mcqs.append(result)

    final_output = "\n\n".join(mcqs)

    return jsonify({
        "mcqs": final_output,
        "short_questions": final_output,
        "answers": final_output
    })

# ---------------- PDF DOWNLOAD ----------------

def create_pdf(content, title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    story = [
        Paragraph(title, styles["Heading1"]),
        Spacer(1, 10),
        Paragraph(content.replace("\n", "<br/>"), styles["Normal"])
    ]

    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route("/download_questions_pdf", methods=["POST"])
def download_q():
    data = request.json

    pdf = create_pdf(
        data.get("mcqs", "") + "\n\n" + data.get("short_questions", ""),
        "Questions"
    )

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=questions.pdf"
    return response

@app.route("/download_answers_pdf", methods=["POST"])
def download_a():
    data = request.json

    pdf = create_pdf(data.get("answers", ""), "Answers")

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=answers.pdf"
    return response

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)