from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import os, uuid, time, hashlib, pickle
from datetime import datetime, timedelta
from io import BytesIO

import chromadb
from chromadb.utils import embedding_functions
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from gpt4all import GPT4All
from ingest import process_single_pdf

# ---------------- APP ----------------
app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "rulebook_docs"
MODEL_NAME = "Phi-3-mini-4k-instruct-q4.gguf"
MODEL_PATH = "models"

CACHE_DIR = "cache"
QUESTIONS_CACHE_FILE = os.path.join(CACHE_DIR, "questions_cache.pkl")

TEACHER_API_KEY = "teacher123"  # 🔐 change this

os.makedirs(CACHE_DIR, exist_ok=True)

# ---------------- AUTH ----------------
def check_auth(req):
    return req.headers.get("x-api-key") == TEACHER_API_KEY

# ---------------- CACHE ----------------
class PersistentCache:
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.cache = {}
        self.load()

    def load(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "rb") as f:
                    self.cache = pickle.load(f)
            except:
                self.cache = {}

    def save(self):
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.cache, f)

    def get(self, key):
        if key in self.cache:
            item = self.cache[key]
            if datetime.now() < item["expiry"]:
                return item["data"]
        return None

    def set(self, key, data, ttl=86400):
        self.cache[key] = {
            "data": data,
            "expiry": datetime.now() + timedelta(seconds=ttl)
        }
        self.save()

questions_cache = PersistentCache(QUESTIONS_CACHE_FILE)

# ---------------- GLOBAL ----------------
CURRENT_SESSION_ID = None
CURRENT_FILE_HASH = None

# ---------------- INIT ----------------
embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_model
)

model = GPT4All(
    model_name=MODEL_NAME,
    model_path=MODEL_PATH,
    device="cpu"
)

# ---------------- HELPERS ----------------
def get_file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def generate(prompt):
    with model.chat_session():
        return model.generate(prompt, max_tokens=400, temp=0.4)

# ---------------- PDF ----------------
def create_questions_pdf(mcqs, short_q, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    story = []
    title = Paragraph(f"Question Bank: {filename}", styles["Heading1"])
    story.append(title)
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph(mcqs.replace("\n", "<br/>"), styles["Normal"]))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(short_q.replace("\n", "<br/>"), styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer

def create_answer_pdf(ans, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    story = []
    story.append(Paragraph(f"Answer Key: {filename}", styles["Heading1"]))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(ans.replace("\n", "<br/>"), styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------- ROUTES ----------------

@app.route("/upload", methods=["POST"])
def upload():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    global CURRENT_SESSION_ID, CURRENT_FILE_HASH

    file = request.files["file"]
    os.makedirs("data", exist_ok=True)

    path = os.path.join("data", file.filename)
    file.save(path)

    CURRENT_FILE_HASH = get_file_hash(path)
    CURRENT_SESSION_ID = str(uuid.uuid4())

    process_single_pdf(path, category="course", session_id=CURRENT_SESSION_ID)

    return jsonify({"message": "Upload successful"})


@app.route("/generate_questions", methods=["POST"])
def generate_questions():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    global CURRENT_SESSION_ID, CURRENT_FILE_HASH

    if not CURRENT_SESSION_ID:
        return jsonify({"error": "Upload PDF first"})

    # CACHE
    cached = questions_cache.get(CURRENT_FILE_HASH)
    if cached:
        return jsonify(cached)

    results = collection.get(where={"session_id": CURRENT_SESSION_ID})
    docs = results.get("documents", [])

    content = "\n".join(docs)[:2500]

    # MCQs
    mcq_prompt = f"""
Generate 5 MCQs:

{content}

Format:
Q1:
A)
B)
C)
D)
Answer:
"""
    mcqs = generate(mcq_prompt)

    # Short Questions
    short_prompt = f"""
Generate 2 short questions:

{content}

Format:
SA1:
SA2:
"""
    short_q = generate(short_prompt)

    # Answer key
    answer_prompt = f"""
Provide answers:

MCQs:
{mcqs}

Short:
{short_q}
"""
    answers = generate(answer_prompt)

    response = {
        "mcqs": mcqs,
        "short_questions": short_q,
        "answers": answers
    }

    questions_cache.set(CURRENT_FILE_HASH, response)

    return jsonify(response)


@app.route("/download_questions_pdf", methods=["POST"])
def download_questions_pdf():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    pdf = create_questions_pdf(
        data["mcqs"],
        data["short_questions"],
        data.get("filename", "doc")
    )

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=questions.pdf"
    return response


@app.route("/download_answers_pdf", methods=["POST"])
def download_answers_pdf():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    pdf = create_answer_pdf(
        data["answers"],
        data.get("filename", "doc")
    )

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=answers.pdf"
    return response


@app.route("/data/<path:filename>")
def serve_pdf(filename):
    return send_from_directory("data", filename)


# ---------------- RUN ----------------
if __name__ == "__main__":
    print("🚀 Teacher MCQ Generator Running...")
    app.run(debug=True)