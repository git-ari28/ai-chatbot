import os
import hashlib
import chromadb

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.utils import embedding_functions

# ---------------- CONFIG ----------------
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "rulebook_docs"

# ---------------- HELPERS ----------------
def hash_text(text):
    return hashlib.sha1(text.encode()).hexdigest()[:10]

def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_model
    )

# ---------------- MAIN FUNCTION ----------------
def process_single_pdf(file_path, category="general", session_id=None):
    print("\n📄 Processing:", file_path)
    print("📂 Category:", category)

    if session_id:
        print("🎯 Session ID:", session_id)

    # ---------- LOAD PDF ----------
    loader = PyMuPDFLoader(file_path)
    docs = loader.load()

    # ---------- SPLIT ----------
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = splitter.split_documents(docs)

    texts, metas, ids = [], [], []

    for c in chunks:
        text = c.page_content.strip()

        # 🔥 FIX 1: Less strict filter (IMPORTANT)
        if len(text) < 30:
            continue

        pdf = os.path.basename(file_path)
        page = c.metadata.get("page", 0)

        h = hash_text(text)

        # 🔥 FIX 2: SESSION-AWARE UNIQUE ID
        if session_id:
            cid = f"{session_id}_{pdf}_{page}_{h}"
        else:
            cid = f"{pdf}_{page}_{h}"

        # ---------- STORE ----------
        texts.append(text)

        metadata = {
            "pdf": pdf,
            "page": page,
            "category": category
        }

        # 🔥 FIX 3: Only attach session for course PDFs
        if session_id:
            metadata["session_id"] = session_id

        metas.append(metadata)
        ids.append(cid)

    # ---------- DB ----------
    collection = get_collection()

    # 🔥 FIX 4: REMOVE duplicate check (important for session-based system)
    if not texts:
        print("⚠️ No valid text extracted")
        return

    collection.add(
        documents=texts,
        metadatas=metas,
        ids=ids
    )

    print("✅ Added", len(texts), "chunks")