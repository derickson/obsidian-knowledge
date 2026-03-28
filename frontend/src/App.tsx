import { useState } from "react";

interface SearchResult {
  path: string;
  title: string;
  score: number;
  tags: string[];
}

export default function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [mode, setMode] = useState<"fulltext" | "semantic">("fulltext");

  const handleSearch = async () => {
    if (!query.trim()) return;
    const endpoint =
      mode === "semantic" ? "/api/notes/semantic-search" : "/api/notes/search";
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, size: 20 }),
    });
    const data = await resp.json();
    setResults(data.results);
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24 }}>
      <h1>Obsidian Knowledge</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search notes..."
          style={{ flex: 1, padding: 8 }}
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as "fulltext" | "semantic")}
        >
          <option value="fulltext">Full-text</option>
          <option value="semantic">Semantic</option>
        </select>
        <button onClick={handleSearch}>Search</button>
      </div>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {results.map((r) => (
          <li
            key={r.path}
            style={{
              padding: 12,
              borderBottom: "1px solid #eee",
            }}
          >
            <strong>{r.title}</strong>{" "}
            <span style={{ color: "#888" }}>({r.path})</span>
            {r.tags?.length > 0 && (
              <div style={{ fontSize: 12, color: "#666" }}>
                {r.tags.map((t) => `#${t}`).join(" ")}
              </div>
            )}
            <div style={{ fontSize: 12, color: "#aaa" }}>
              Score: {r.score?.toFixed(3)}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
