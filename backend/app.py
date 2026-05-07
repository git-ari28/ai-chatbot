from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import os, uuid
from io import BytesIO
import requests
import fitz  # PyMuPDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
CORS(app)

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
    return text[:500]  # LIMIT to avoid crashes

# ---------------- OLLAMA ----------------
def generate(prompt):
    res = requests.post(OLLAMA_URL, json={
        "model": "phi3:mini",
        "prompt": prompt,
        "stream": False
    })
    return res.json()["response"]

# ---------------- ROUTES ----------------

@app.route("/upload", methods=["POST"])
def upload():
    global stored_text

    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    file = request.files["file"]
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
        return jsonify({"error": "Upload PDF first"})

    # MCQs
    mcq_prompt = f"""
Generate 5 MCQs with answers:

{stored_text}

Format:
Q1:
A)
B)
C)
D)
Answer:
"""
    mcqs = generate(mcq_prompt)

    # Short
    short_prompt = f"""
Generate 3 short answer questions:

{stored_text}
"""
    short_q = generate(short_prompt)

    # Answers
    answer_prompt = f"""
Give answers for:

{mcqs}
{short_q}
"""
    answers = generate(answer_prompt)

    return jsonify({
        "mcqs": mcqs,
        "short_questions": short_q,
        "answers": answers
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
        data["mcqs"] + "\n\n" + data["short_questions"],
        "Questions"
    )

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=questions.pdf"
    return response

@app.route("/download_answers_pdf", methods=["POST"])
def download_a():
    data = request.json
    pdf = create_pdf(data["answers"], "Answers")

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=answers.pdf"
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)