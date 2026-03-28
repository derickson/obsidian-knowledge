import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

declare const __API_PREFIX__: string;
const API = `${__API_PREFIX__}/api/notes/`;
const CHAT_API = `${__API_PREFIX__}/api/chat/`;

interface NoteListItem {
  path: string;
  title: string;
  score?: number;
  tags?: string[];
  last_modified?: number;
}

interface NoteDetail {
  path: string;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  tags: string[];
  wikilinks: string[];
  last_modified: number;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<NoteListItem[]>([]);
  const [selected, setSelected] = useState<NoteDetail | null>(null);
  const [mode, setMode] = useState<"fulltext" | "semantic">("semantic");
  const [dark, setDark] = useState(
    window.matchMedia("(prefers-color-scheme: dark)").matches,
  );

  // Chat state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatModel, setChatModel] = useState("claude-haiku-4-5-20251001");
  const [chatStreaming, setChatStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load recent notes on mount
  useEffect(() => {
    fetch(`${API}recent/?size=20`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.results && setResults(d.results))
      .catch(() => {});
  }, []);

  // Listen for OS theme changes
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, activeTool]);

  const handleSearch = async () => {
    if (!query.trim()) {
      const resp = await fetch(`${API}recent/?size=20`);
      const data = await resp.json();
      if (data?.results) setResults(data.results);
      return;
    }
    const endpoint =
      mode === "semantic" ? `${API}semantic-search/` : `${API}search/`;
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, size: 20 }),
    });
    const data = await resp.json();
    if (data?.results) setResults(data.results);
  };

  const handleSelect = async (path: string) => {
    const resp = await fetch(`${API}${encodeURIComponent(path)}`);
    if (resp.ok) {
      setSelected(await resp.json());
    }
  };

  const handleChatSend = async () => {
    if (!chatInput.trim() || chatStreaming) return;

    const userMsg: ChatMessage = { role: "user", content: chatInput };
    const updated = [...chatMessages, userMsg];
    setChatMessages([...updated, { role: "assistant", content: "" }]);
    setChatInput("");
    setChatStreaming(true);
    setActiveTool(null);

    try {
      const apiMessages = updated.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await fetch(CHAT_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: apiMessages,
          model: chatModel,
          focused_note_path: selected?.path || null,
        }),
      });

      if (!response.ok || !response.body) {
        setChatMessages((prev) => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = {
            role: "assistant",
            content: "Error: failed to connect to chat service.",
          };
          return msgs;
        });
        setChatStreaming(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === "text") {
              setChatMessages((prev) => {
                const msgs = [...prev];
                const last = msgs[msgs.length - 1];
                msgs[msgs.length - 1] = {
                  ...last,
                  content: last.content + data.content,
                };
                return msgs;
              });
            } else if (data.type === "tool_use_start") {
              setActiveTool(data.name);
            } else if (data.type === "tool_result") {
              setActiveTool(null);
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch {
      setChatMessages((prev) => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = {
          role: "assistant",
          content: "Error: connection lost.",
        };
        return msgs;
      });
    }

    setChatStreaming(false);
    setActiveTool(null);
  };

  const theme = dark ? themes.dark : themes.light;

  return (
    <div
      style={{
        ...theme.root,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}
    >
      {/* Header */}
      <header style={theme.header}>
        <h1 style={{ margin: 0, fontSize: 18 }}>Obsidian Knowledge</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setChatOpen(!chatOpen)}
            style={theme.headerButton}
          >
            {chatOpen ? "Close Chat" : "Chat"}
          </button>
          <button
            onClick={() => setDark(!dark)}
            style={theme.headerButton}
            title="Toggle theme"
          >
            {dark ? "Light" : "Dark"}
          </button>
        </div>
      </header>

      {/* Search bar */}
      <div style={theme.searchBar}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search notes..."
          style={theme.searchInput}
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as "fulltext" | "semantic")}
          style={theme.select}
        >
          <option value="semantic">Semantic</option>
          <option value="fulltext">Full-text</option>
        </select>
        <button onClick={handleSearch} style={theme.button}>
          Search
        </button>
      </div>

      {/* Main content: list + detail + chat */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left panel: results list */}
        <div style={theme.listPanel}>
          {results.map((r) => (
            <div
              key={r.path}
              onClick={() => handleSelect(r.path)}
              style={{
                ...theme.listItem,
                ...(selected?.path === r.path ? theme.listItemSelected : {}),
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14 }}>{r.title}</div>
              <div style={{ fontSize: 11, opacity: 0.6 }}>{r.path}</div>
              {r.tags && r.tags.length > 0 && (
                <div style={{ fontSize: 11, opacity: 0.5, marginTop: 2 }}>
                  {r.tags.map((t) => `#${t}`).join(" ")}
                </div>
              )}
            </div>
          ))}
          {results.length === 0 && (
            <div style={{ padding: 16, opacity: 0.5, fontSize: 13 }}>
              No results
            </div>
          )}
        </div>

        {/* Middle panel: note detail */}
        <div style={theme.detailPanel}>
          {selected ? (
            <>
              <div style={theme.detailHeader}>
                <h2 style={{ margin: 0, fontSize: 20 }}>{selected.title}</h2>
                <div style={{ fontSize: 12, opacity: 0.5, marginTop: 4 }}>
                  {selected.path}
                  {selected.last_modified &&
                    ` · ${new Date(selected.last_modified * 1000).toLocaleString()}`}
                </div>
                {selected.tags.length > 0 && (
                  <div
                    style={{
                      marginTop: 6,
                      display: "flex",
                      gap: 4,
                      flexWrap: "wrap",
                    }}
                  >
                    {selected.tags.map((t) => (
                      <span key={t} style={theme.tag}>
                        #{t}
                      </span>
                    ))}
                  </div>
                )}
                {selected.wikilinks.length > 0 && (
                  <div
                    style={{
                      marginTop: 6,
                      display: "flex",
                      gap: 4,
                      flexWrap: "wrap",
                    }}
                  >
                    {selected.wikilinks.map((link) => (
                      <span
                        key={link}
                        style={theme.wikilink}
                        onClick={() => handleSelect(`${link}.md`)}
                      >
                        [[{link}]]
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div style={theme.markdownBody}>
                <ReactMarkdown>{selected.content}</ReactMarkdown>
              </div>
            </>
          ) : (
            <div style={{ padding: 32, opacity: 0.4, fontSize: 14 }}>
              Select a note to view its content
            </div>
          )}
        </div>

        {/* Right panel: chat */}
        {chatOpen && (
          <div style={theme.chatPanel}>
            {/* Model selector + clear */}
            <div style={theme.chatHeader}>
              <select
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
                style={{ ...theme.select, flex: 1 }}
              >
                <option value="claude-haiku-4-5-20251001">Haiku 4.5</option>
                <option value="claude-opus-4-6">Opus 4.6</option>
              </select>
              <button
                onClick={() => setChatMessages([])}
                style={theme.headerButton}
                title="Clear chat"
              >
                Clear
              </button>
            </div>

            {/* Messages */}
            <div style={theme.chatMessages}>
              {chatMessages.length === 0 && (
                <div style={{ opacity: 0.4, fontSize: 13, padding: 8 }}>
                  Ask questions about your knowledge base...
                </div>
              )}
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  style={
                    msg.role === "user"
                      ? theme.chatUserMsg
                      : theme.chatAssistantMsg
                  }
                >
                  {msg.role === "assistant" ? (
                    <ReactMarkdown>{msg.content || "..."}</ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
              ))}
              {activeTool && (
                <div style={theme.chatToolIndicator}>
                  Using tool: {activeTool}...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div style={theme.chatInputArea}>
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleChatSend()}
                placeholder="Ask about your notes..."
                style={theme.chatInput}
                disabled={chatStreaming}
              />
              <button
                onClick={handleChatSend}
                disabled={chatStreaming}
                style={theme.button}
              >
                Send
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const shared = {
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
};

const themes = {
  light: {
    root: { ...shared, background: "#ffffff", color: "#1a1a1a" },
    header: {
      display: "flex" as const,
      justifyContent: "space-between" as const,
      alignItems: "center" as const,
      padding: "12px 16px",
      borderBottom: "1px solid #e0e0e0",
      background: "#fafafa",
    },
    headerButton: {
      background: "none",
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: "4px 12px",
      cursor: "pointer" as const,
      fontSize: 13,
      color: "#1a1a1a",
    },
    searchBar: {
      display: "flex" as const,
      gap: 8,
      padding: "10px 16px",
      borderBottom: "1px solid #e0e0e0",
      background: "#fafafa",
    },
    searchInput: {
      flex: 1,
      padding: "8px 12px",
      border: "1px solid #ccc",
      borderRadius: 6,
      fontSize: 14,
      background: "#fff",
      color: "#1a1a1a",
    },
    select: {
      padding: "8px 12px",
      border: "1px solid #ccc",
      borderRadius: 6,
      fontSize: 13,
      background: "#fff",
      color: "#1a1a1a",
    },
    button: {
      padding: "8px 16px",
      border: "none",
      borderRadius: 6,
      background: "#7c3aed",
      color: "#fff",
      fontSize: 13,
      cursor: "pointer" as const,
    },
    listPanel: {
      width: 280,
      minWidth: 280,
      borderRight: "1px solid #e0e0e0",
      overflowY: "auto" as const,
      background: "#fafafa",
    },
    listItem: {
      padding: "10px 16px",
      borderBottom: "1px solid #eee",
      cursor: "pointer" as const,
    },
    listItemSelected: { background: "#ede9fe" },
    detailPanel: {
      flex: 1,
      overflowY: "auto" as const,
      display: "flex" as const,
      flexDirection: "column" as const,
    },
    detailHeader: {
      padding: "16px 24px",
      borderBottom: "1px solid #e0e0e0",
    },
    tag: {
      fontSize: 11,
      padding: "2px 8px",
      borderRadius: 12,
      background: "#ede9fe",
      color: "#7c3aed",
    },
    wikilink: {
      fontSize: 11,
      padding: "2px 8px",
      borderRadius: 12,
      background: "#dbeafe",
      color: "#2563eb",
      cursor: "pointer" as const,
    },
    markdownBody: {
      padding: "16px 24px",
      flex: 1,
      lineHeight: 1.7,
      fontSize: 15,
    },
    chatPanel: {
      width: 400,
      minWidth: 400,
      borderLeft: "1px solid #e0e0e0",
      display: "flex" as const,
      flexDirection: "column" as const,
      background: "#fafafa",
    },
    chatHeader: {
      display: "flex" as const,
      gap: 8,
      padding: "8px 12px",
      borderBottom: "1px solid #e0e0e0",
    },
    chatMessages: {
      flex: 1,
      overflowY: "auto" as const,
      padding: 12,
      display: "flex" as const,
      flexDirection: "column" as const,
      gap: 8,
    },
    chatUserMsg: {
      alignSelf: "flex-end" as const,
      background: "#7c3aed",
      color: "#fff",
      padding: "8px 12px",
      borderRadius: 12,
      maxWidth: "85%",
      fontSize: 14,
      whiteSpace: "pre-wrap" as const,
    },
    chatAssistantMsg: {
      alignSelf: "flex-start" as const,
      background: "#f0f0f0",
      color: "#1a1a1a",
      padding: "8px 12px",
      borderRadius: 12,
      maxWidth: "90%",
      fontSize: 14,
      lineHeight: 1.6,
    },
    chatToolIndicator: {
      alignSelf: "center" as const,
      fontSize: 12,
      opacity: 0.6,
      fontStyle: "italic" as const,
      padding: "4px 8px",
    },
    chatInputArea: {
      display: "flex" as const,
      gap: 8,
      padding: "8px 12px",
      borderTop: "1px solid #e0e0e0",
    },
    chatInput: {
      flex: 1,
      padding: "8px 12px",
      border: "1px solid #ccc",
      borderRadius: 6,
      fontSize: 14,
      background: "#fff",
      color: "#1a1a1a",
    },
  },
  dark: {
    root: { ...shared, background: "#1a1a2e", color: "#e0e0e0" },
    header: {
      display: "flex" as const,
      justifyContent: "space-between" as const,
      alignItems: "center" as const,
      padding: "12px 16px",
      borderBottom: "1px solid #2a2a4a",
      background: "#16162a",
    },
    headerButton: {
      background: "none",
      border: "1px solid #444",
      borderRadius: 6,
      padding: "4px 12px",
      cursor: "pointer" as const,
      fontSize: 13,
      color: "#e0e0e0",
    },
    searchBar: {
      display: "flex" as const,
      gap: 8,
      padding: "10px 16px",
      borderBottom: "1px solid #2a2a4a",
      background: "#16162a",
    },
    searchInput: {
      flex: 1,
      padding: "8px 12px",
      border: "1px solid #444",
      borderRadius: 6,
      fontSize: 14,
      background: "#1e1e3a",
      color: "#e0e0e0",
    },
    select: {
      padding: "8px 12px",
      border: "1px solid #444",
      borderRadius: 6,
      fontSize: 13,
      background: "#1e1e3a",
      color: "#e0e0e0",
    },
    button: {
      padding: "8px 16px",
      border: "none",
      borderRadius: 6,
      background: "#7c3aed",
      color: "#fff",
      fontSize: 13,
      cursor: "pointer" as const,
    },
    listPanel: {
      width: 280,
      minWidth: 280,
      borderRight: "1px solid #2a2a4a",
      overflowY: "auto" as const,
      background: "#16162a",
    },
    listItem: {
      padding: "10px 16px",
      borderBottom: "1px solid #2a2a4a",
      cursor: "pointer" as const,
    },
    listItemSelected: { background: "#2d1b69" },
    detailPanel: {
      flex: 1,
      overflowY: "auto" as const,
      display: "flex" as const,
      flexDirection: "column" as const,
    },
    detailHeader: {
      padding: "16px 24px",
      borderBottom: "1px solid #2a2a4a",
    },
    tag: {
      fontSize: 11,
      padding: "2px 8px",
      borderRadius: 12,
      background: "#2d1b69",
      color: "#a78bfa",
    },
    wikilink: {
      fontSize: 11,
      padding: "2px 8px",
      borderRadius: 12,
      background: "#1e3a5f",
      color: "#60a5fa",
      cursor: "pointer" as const,
    },
    markdownBody: {
      padding: "16px 24px",
      flex: 1,
      lineHeight: 1.7,
      fontSize: 15,
    },
    chatPanel: {
      width: 400,
      minWidth: 400,
      borderLeft: "1px solid #2a2a4a",
      display: "flex" as const,
      flexDirection: "column" as const,
      background: "#16162a",
    },
    chatHeader: {
      display: "flex" as const,
      gap: 8,
      padding: "8px 12px",
      borderBottom: "1px solid #2a2a4a",
    },
    chatMessages: {
      flex: 1,
      overflowY: "auto" as const,
      padding: 12,
      display: "flex" as const,
      flexDirection: "column" as const,
      gap: 8,
    },
    chatUserMsg: {
      alignSelf: "flex-end" as const,
      background: "#7c3aed",
      color: "#fff",
      padding: "8px 12px",
      borderRadius: 12,
      maxWidth: "85%",
      fontSize: 14,
      whiteSpace: "pre-wrap" as const,
    },
    chatAssistantMsg: {
      alignSelf: "flex-start" as const,
      background: "#1e1e3a",
      color: "#e0e0e0",
      padding: "8px 12px",
      borderRadius: 12,
      maxWidth: "90%",
      fontSize: 14,
      lineHeight: 1.6,
    },
    chatToolIndicator: {
      alignSelf: "center" as const,
      fontSize: 12,
      opacity: 0.6,
      fontStyle: "italic" as const,
      padding: "4px 8px",
    },
    chatInputArea: {
      display: "flex" as const,
      gap: 8,
      padding: "8px 12px",
      borderTop: "1px solid #2a2a4a",
    },
    chatInput: {
      flex: 1,
      padding: "8px 12px",
      border: "1px solid #444",
      borderRadius: 6,
      fontSize: 14,
      background: "#1e1e3a",
      color: "#e0e0e0",
    },
  },
};
