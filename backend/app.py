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

# ✅ FIXED CORS
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Content-Type", "x-api-key"],
    methods=["GET", "POST", "OPTIONS"]
)

OLLAMA_URL = "http://ai-chatbot-ollama-1:11434/api/generate"
API_KEY = "teacher123"

stored_text = ""

# ---------------- AUTH ----------------
def check_auth(req):
    return req.headers.get("x-api-key") == API_KEY

# ---------------- PDF TEXT EXTRACTION ----------------
def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()

    return text[:300]  # ✅ small input = faster + stable

# ---------------- OLLAMA ----------------
def generate(prompt):
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": "tinyllama",   # ✅ lightweight model
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        data = res.json()
        print("🔍 Ollama response:", data)

        return data.get("response", "No response from model")

    except Exception as e:
        print("❌ Ollama error:", str(e))
        return "Error generating response"

# ---------------- ROUTES ----------------

@app.route("/upload", methods=["POST"])
def upload():
    global stored_text

    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", file.filename)
    file.save(path)

    stored_text = extract_text(path)

    return jsonify({"message": "PDF uploaded successfully"})

@app.route("/generate_questions", methods=["POST"])
def generate_questions():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    if not stored_text:
        return jsonify({"error": "Upload PDF first"}), 400

    print("🔥 Generating questions...")

    # ✅ SINGLE FAST PROMPT (important)
    prompt = f"""
You are a teacher creating exam questions.

Rules:
- Be accurate
- Do not hallucinate facts
- Keep answers short

Generate:
1) 2 MCQs with options A-D and correct answer
2) 1 short answer question with answer

Text:
{stored_text}
"""

    result = generate(prompt)

    return jsonify({
        "mcqs": result,
        "short_questions": result,
        "answers": result
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