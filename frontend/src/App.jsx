import { useState } from "react";

const API = "http://20.244.24.129:5000";
const API_KEY = "teacher123";

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  const upload = async () => {
    if (!file) return alert("Upload PDF");

    const fd = new FormData();
    fd.append("file", file);

    setLoading(true);

    const res = await fetch(`${API}/upload`, {
      method: "POST",
      headers: { "x-api-key": API_KEY },
      body: fd
    });

    await res.json();
    setLoading(false);
    alert("Uploaded");
  };

  const generate = async () => {
    setLoading(true);

    const res = await fetch(`${API}/generate_questions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
      }
    });

    const result = await res.json();
    setData(result);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">

        <h1 className="text-2xl font-bold mb-4 text-center">
          📘 MCQ Generator
        </h1>

        <input type="file" onChange={(e) => setFile(e.target.files[0])} />

        <div className="flex gap-3 mt-3">
          <button onClick={upload} className="bg-blue-500 text-white px-4 py-2 rounded">
            Upload
          </button>

          <button onClick={generate} className="bg-green-500 text-white px-4 py-2 rounded">
            Generate
          </button>
        </div>

        {loading && <p className="mt-3">Processing...</p>}

        {data && (
          <div className="mt-5 space-y-4">
            <pre className="bg-gray-200 p-3">{data.mcqs}</pre>
            <pre className="bg-gray-200 p-3">{data.short_questions}</pre>
            <pre className="bg-gray-200 p-3">{data.answers}</pre>
          </div>
        )}

      </div>
    </div>
  );
}