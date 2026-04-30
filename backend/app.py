from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, chromadb, uuid, base64, requests, re, time
from hashlib import md5
from io import BytesIO

from gpt4all import GPT4All
from chromadb.utils import embedding_functions
from ingest import process_single_pdf
from pdf2image import convert_from_path
from langdetect import detect
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "rulebook_docs"

MODEL_NAME = "Phi-3-mini-4k-instruct-q4.gguf"
MODEL_PATH = "models"

OLLAMA_URL = "http://ollama:11434/api/generate"
VISION_MODEL = "llava"

MAX_TOKENS = 300
N_RESULTS = 2

# ---------------- GLOBAL ----------------
CURRENT_SESSION_ID = None
CURRENT_PDF_PATH = None
response_cache = {}

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
    n_threads=8,
    n_ctx=1024
)

# ---------------- CACHE ----------------
def get_cache_key(prompt):
    return md5(prompt.encode()).hexdigest()

def generate(prompt, max_tokens=MAX_TOKENS, temp=0.1):
    key = get_cache_key(prompt)
    if key in response_cache:
        return response_cache[key]

    with model.chat_session():
        res = model.generate(
            prompt,
            max_tokens=max_tokens,
            temp=temp,
            top_k=40,
            top_p=0.9
        )

    response_cache[key] = res
    return res

# ---------------- TRANSLATION ----------------
def translate_to_en(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

def translate_back(text, lang):
    try:
        return GoogleTranslator(source='en', target=lang).translate(text)
    except:
        return text

# ---------------- RAG ----------------
def retrieve_context(query):
    results = collection.query(
        query_texts=[query],
        n_results=N_RESULTS,
        where={"session_id": CURRENT_SESSION_ID}
    )

    docs = results.get("documents", [[]])[0]
    return "\n".join(docs)[:2000]

# ---------------- VISION ----------------
def extract_page_image(pdf_path, page):
    try:
        pages = convert_from_path(pdf_path, first_page=page, last_page=page, dpi=120)
        path = f"temp_{page}.jpg"
        pages[0].save(path, "JPEG")
        return path
    except:
        return None

def ask_llava(image_path, question):
    try:
        with open(image_path, "rb") as f:
            img = base64.b64encode(f.read()).decode()

        payload = {
            "model": VISION_MODEL,
            "prompt": question,
            "images": [img],
            "stream": False
        }

        res = requests.post(OLLAMA_URL, json=payload, timeout=60)
        return res.json().get("response", "")
    except:
        return "⚠️ Vision model failed"

# ---------------- HELPERS ----------------
def trim_to_5_mcqs(text):
    pattern = r"(Q[1-5]:.*?Answer:\s*[A-D])"
    return "\n\n".join(re.findall(pattern, text, re.DOTALL)[:5])

# ---------------- ROUTES ----------------

@app.route('/upload', methods=['POST'])
def upload():
    global CURRENT_SESSION_ID, CURRENT_PDF_PATH

    file = request.files['file']
    os.makedirs("data", exist_ok=True)

    path = os.path.join("data", file.filename)
    file.save(path)

    CURRENT_PDF_PATH = path
    CURRENT_SESSION_ID = str(uuid.uuid4())

    process_single_pdf(path, category="course", session_id=CURRENT_SESSION_ID)

    return jsonify({"message": "Upload successful"})

# ---------------- ASK ----------------
@app.route('/ask', methods=['POST'])
def ask():
    global CURRENT_PDF_PATH

    data = request.get_json()
    q = data.get("question", "")

    try:
        lang = detect(q)
    except:
        lang = "en"

    q_en = translate_to_en(q)

    # 📸 Vision trigger
    match = re.search(r'page\s*(\d+)', q_en.lower())
    if match and CURRENT_PDF_PATH:
        page = int(match.group(1))
        img = extract_page_image(CURRENT_PDF_PATH, page)

        if img:
            ans = ask_llava(img, q_en)
        else:
            ans = "⚠️ Could not extract page image"

    else:
        context = retrieve_context(q_en)
        prompt = f"Context:\n{context}\n\nQuestion: {q_en}\nAnswer briefly:"
        ans = generate(prompt)

    if lang != "en":
        ans = translate_back(ans, lang)

    return jsonify({"answer": ans})

# ---------------- SUMMARY ----------------
@app.route('/summarize', methods=['POST'])
def summarize():
    results = collection.get(where={"session_id": CURRENT_SESSION_ID})
    docs = results.get("documents", [])

    content = "\n".join(docs)[:4000]

    if not content.strip():
        return jsonify({"summary": "⚠️ No content found"})

    prompt = f"""
Summarize the document.

- 5 bullet points
- short and clear

Text:
{content}
"""

    summary = generate(prompt)
    return jsonify({"summary": summary})

# ---------------- QUESTIONS ----------------
@app.route('/generate_questions', methods=['POST'])
def generate_questions():
    results = collection.get(where={"session_id": CURRENT_SESSION_ID})
    docs = results.get("documents", [])

    content = "\n".join(docs)[:2000]

    # MCQs
    mcq_prompt = f"""
Generate EXACTLY 5 MCQs.

Q1:
A)
B)
C)
D)
Answer:

Q2:
Q3:
Q4:
Q5:

Text:
{content}
"""
    mcqs_raw = generate(mcq_prompt)
    mcqs_clean = trim_to_5_mcqs(mcqs_raw)

    mcqs_only = re.sub(r"Answer:\s*[A-D]", "", mcqs_clean)
    mcq_answers = re.findall(r"Answer:\s*([A-D])", mcqs_clean)

    # SHORT ANSWERS
    short_prompt = f"""
Generate EXACTLY 2 short answer questions with answers.

SA1:
Answer:
- 
- 
- 

SA2:
Answer:
- 
- 
- 

Text:
{content}
"""
    short_raw = generate(short_prompt)

    if "SA1" not in short_raw:
        short_final = """SA1: What is the function of the heart?
Answer:
- Pumps blood
- Supplies oxygen
- Removes waste

SA2: What are heart chambers?
Answer:
- Atria and ventricles
- Right and left sides
- Circulation system"""
    else:
        short_final = short_raw

    # ANSWER KEY
    answer_key = "SECTION 1: MCQs\n"
    for i, ans in enumerate(mcq_answers, 1):
        answer_key += f"Q{i}: {ans}\n"

    answer_key += "\nSECTION 2: SHORT ANSWERS\n" + short_final

    return jsonify({
        "mcqs_only": mcqs_only,
        "mcqs_display": mcqs_clean,
        "short_answers_only": short_final,
        "short_answers_display": short_final,
        "answer_key": answer_key,
        "answer_key_display": answer_key
    })

# ---------------- SERVE PDF ----------------
@app.route('/data/<path:filename>')
def serve_pdf(filename):
    return send_from_directory("data", filename)

# ---------------- RUN ----------------
if __name__ == "__main__":
    print("🚀 FULL SYSTEM RUNNING (RAG + VISION + QUESTIONS + SUMMARY)")
    app.run(debug=True, use_reloader=False)