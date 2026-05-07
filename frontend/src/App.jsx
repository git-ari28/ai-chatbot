import { useState } from "react";

const API = "http://localhost:5000";
const API_KEY = "teacher123";

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  // Upload PDF
  const handleUpload = async () => {
    if (!file) return alert("Upload a PDF first");

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);

    try {
      const res = await fetch(`${API}/upload`, {
        method: "POST",
        headers: {
          "x-api-key": API_KEY
        },
        body: formData
      });

      const result = await res.json();
      alert(result.message || "Uploaded");
    } catch (err) {
      alert("Upload failed");
    }

    setLoading(false);
  };

  // Generate Questions
  const generateQuestions = async () => {
    setLoading(true);

    try {
      const res = await fetch(`${API}/generate_questions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": API_KEY
        }
      });

      const result = await res.json();
      setData(result);
    } catch (err) {
      alert("Generation failed");
    }

    setLoading(false);
  };

  // Download PDF
  const downloadPDF = async (type) => {
    const endpoint =
      type === "questions"
        ? "/download_questions_pdf"
        : "/download_answers_pdf";

    const payload =
      type === "questions"
        ? {
            mcqs: data.mcqs,
            short_questions: data.short_questions
          }
        : {
            answers: data.answers
          };

    const res = await fetch(`${API}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
      },
      body: JSON.stringify(payload)
    });

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `${type}.pdf`;
    a.click();
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-4xl mx-auto bg-white shadow-lg rounded-2xl p-6">

        <h1 className="text-3xl font-bold mb-6 text-center">
          📘 Teacher MCQ Generator
        </h1>

        {/* Upload Section */}
        <div className="mb-6">
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files[0])}
            className="mb-3"
          />

          <button
            onClick={handleUpload}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg mr-2 hover:bg-blue-700"
          >
            Upload PDF
          </button>
        </div>

        {/* Generate */}
        <div className="mb-6">
          <button
            onClick={generateQuestions}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700"
          >
            Generate Questions
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <p className="text-center text-gray-600">⏳ Processing...</p>
        )}

        {/* Output */}
        {data && (
          <div className="space-y-6">

            {/* MCQs */}
            <div>
              <h2 className="text-xl font-semibold mb-2">📝 MCQs</h2>
              <pre className="bg-gray-200 p-3 rounded whitespace-pre-wrap">
                {data.mcqs}
              </pre>
            </div>

            {/* Short Questions */}
            <div>
              <h2 className="text-xl font-semibold mb-2">✏️ Short Questions</h2>
              <pre className="bg-gray-200 p-3 rounded whitespace-pre-wrap">
                {data.short_questions}
              </pre>
            </div>

            {/* Answers */}
            <div>
              <h2 className="text-xl font-semibold mb-2">✅ Answer Key</h2>
              <pre className="bg-gray-200 p-3 rounded whitespace-pre-wrap">
                {data.answers}
              </pre>
            </div>

            {/* Download Buttons */}
            <div className="flex gap-4">
              <button
                onClick={() => downloadPDF("questions")}
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
              >
                Download Questions PDF
              </button>

              <button
                onClick={() => downloadPDF("answers")}
                className="bg-orange-600 text-white px-4 py-2 rounded hover:bg-orange-700"
              >
                Download Answers PDF
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}