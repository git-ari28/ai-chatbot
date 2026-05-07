import { useState } from "react";

const API = "http://20.244.24.129:5000";
const API_KEY = "teacher123";

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  // 📤 Upload PDF
  const upload = async () => {
    if (!file) return alert("Upload PDF first");

    const fd = new FormData();
    fd.append("file", file);

    setLoading(true);

    try {
      const res = await fetch(`${API}/upload`, {
        method: "POST",
        headers: { "x-api-key": API_KEY },
        body: fd,
      });

      const result = await res.json();
      console.log("UPLOAD:", result);

      alert(result.message || "Uploaded successfully");
    } catch (err) {
      console.error("UPLOAD ERROR:", err);
      alert("Upload failed");
    }

    setLoading(false);
  };

  // ⚡ Generate Questions
  const generate = async () => {
    console.log("🔥 Generate clicked");

    setLoading(true);

    try {
      const res = await fetch(`${API}/generate_questions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": API_KEY,
        },
        body: JSON.stringify({}), // ✅ IMPORTANT FIX
      });

      const result = await res.json();
      console.log("GENERATE RESULT:", result);

      setData(result);
    } catch (err) {
      console.error("❌ GENERATE ERROR:", err);
      alert("Generation failed");
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">

        <h1 className="text-3xl font-bold mb-6 text-center">
          📘 MCQ Generator
        </h1>

        {/* Upload */}
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files[0])}
          className="mb-3"
        />

        <div className="flex gap-3">
          <button
            onClick={upload}
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
          >
            Upload
          </button>

          <button
            onClick={generate}
            className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
          >
            Generate
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <p className="mt-4 text-center text-gray-600">
            ⏳ Processing... (may take 10–30 sec)
          </p>
        )}

        {/* Output */}
        {data && (
          <div className="mt-6 space-y-4">

            <div>
              <h2 className="font-semibold">📝 MCQs</h2>
              <pre className="bg-gray-200 p-3 rounded whitespace-pre-wrap">
                {data.mcqs}
              </pre>
            </div>

            <div>
              <h2 className="font-semibold">✏️ Short Questions</h2>
              <pre className="bg-gray-200 p-3 rounded whitespace-pre-wrap">
                {data.short_questions}
              </pre>
            </div>

            <div>
              <h2 className="font-semibold">✅ Answers</h2>
              <pre className="bg-gray-200 p-3 rounded whitespace-pre-wrap">
                {data.answers}
              </pre>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}