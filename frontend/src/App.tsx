import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

declare const __API_PREFIX__: string;
const API = `${__API_PREFIX__}/api/notes/`;
const CHAT_API = `${__API_PREFIX__}/api/chat/`;

const WIKILINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

function renderWikilinks(text: string): string {
  return text.replace(WIKILINK_RE, (_match, target, alias) => {
    const display = alias || target;
    return `[${display}](/wikilink/${encodeURIComponent(target)})`;
  });
}

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

type MobileView = "list" | "detail" | "chat";

function useIsMobile() {
  const [mobile, setMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);
  return mobile;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<NoteListItem[]>([]);
  const [selected, setSelected] = useState<NoteDetail | null>(null);
  const [dark, setDark] = useState(
    window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
  const [mobileView, setMobileView] = useState<MobileView>("list");

  const [existingNotes, setExistingNotes] = useState<Set<string>>(new Set());

  const [chatOpen, setChatOpen] = useState(window.innerWidth >= 768);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatModel, setChatModel] = useState("claude-haiku-4-5-20251001");
  const [chatStreaming, setChatStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const isMobile = useIsMobile();

  const refreshNoteList = () => {
    fetch(`${API}list/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.notes && setExistingNotes(new Set(d.notes)))
      .catch(() => {});
  };

  useEffect(() => {
    fetch(`${API}recent/?size=20`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.results && setResults(d.results))
      .catch(() => {});
    refreshNoteList();
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

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
    const endpoint = `${API}semantic-search/`;
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
      if (isMobile) setMobileView("detail");
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
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
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
      let notesMutated = false;

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
              if (["create", "delete", "reindex"].includes(data.name)) {
                notesMutated = true;
              }
            } else if (data.type === "tool_result") {
              setActiveTool(null);
            } else if (data.type === "done" && notesMutated) {
              if (selected?.path) {
                handleSelect(selected.path).catch(() => setSelected(null));
              }
              fetch(`${API}recent/?size=20`)
                .then((r) => (r.ok ? r.json() : null))
                .then((d) => d?.results && setResults(d.results))
                .catch(() => {});
              refreshNoteList();
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

  const noteExists = (target: string): boolean => {
    const path = target.endsWith(".md") ? target : `${target}.md`;
    return existingNotes.has(path);
  };

  const mdComponents = {
    a: ({
      href,
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
      // Check for /wikilink/ path prefix
      const wikiPrefix = "/wikilink/";
      const wikilinkTarget = href?.startsWith(wikiPrefix)
        ? decodeURIComponent(href.slice(wikiPrefix.length))
        : null;

      if (wikilinkTarget) {
        const exists = noteExists(wikilinkTarget);
        const linkStyle = exists
          ? (dark ? themes.dark.wikilink : themes.light.wikilink)
          : (dark ? themes.dark.deadWikilink : themes.light.deadWikilink);
        return (
          <a
            {...props}
            href="javascript:void(0)"
            style={linkStyle}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (exists) handleSelect(`${wikilinkTarget}.md`);
            }}
            title={exists ? wikilinkTarget : `${wikilinkTarget} (not yet created)`}
          >
            {children}
          </a>
        );
      }

      // External links open in new tab
      if (href?.startsWith("http://") || href?.startsWith("https://")) {
        return (
          <a href={href} {...props} target="_blank" rel="noopener noreferrer">
            {children} ↗
          </a>
        );
      }

      // Anything else: treat as internal note reference
      const notePath = href?.endsWith(".md") ? href || "" : `${href}.md`;
      const exists = existingNotes.has(notePath);
      const linkStyle = exists
        ? (dark ? themes.dark.wikilink : themes.light.wikilink)
        : (dark ? themes.dark.deadWikilink : themes.light.deadWikilink);
      return (
        <a
          {...props}
          href="javascript:void(0)"
          style={linkStyle}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (exists) handleSelect(notePath);
          }}
          title={exists ? notePath : `${notePath} (not yet created)`}
        >
          {children}
        </a>
      );
    },
  };

  const handleToday = async () => {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const dd = String(now.getDate()).padStart(2, "0");
    const dateStr = `${yyyy}-${mm}-${dd}`;
    const path = `Observations/${dateStr}-Daily.md`;

    // Try to read it first
    const resp = await fetch(`${API}${encodeURIComponent(path)}`);
    if (resp.ok) {
      setSelected(await resp.json());
      if (isMobile) setMobileView("detail");
      return;
    }

    // Create it
    const dayName = now.toLocaleDateString("en-US", { weekday: "long" });
    await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path,
        content: `# Daily Observations — ${dayName}, ${dateStr}\n\n`,
        metadata: {
          title: `Daily Observations ${dateStr}`,
          tags: ["observation", "daily"],
          date: dateStr,
        },
      }),
    });

    // Now read and select it
    const readResp = await fetch(`${API}${encodeURIComponent(path)}`);
    if (readResp.ok) {
      setSelected(await readResp.json());
      if (isMobile) setMobileView("detail");
    }

    // Refresh the list
    fetch(`${API}recent/?size=20`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.results && setResults(d.results))
      .catch(() => {});
  };

  const theme = dark ? themes.dark : themes.light;

  // --- Shared panel renderers ---

  const renderListPanel = () => (
    <div style={isMobile ? theme.listPanelMobile : theme.listPanel}>
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
  );

  const renderDetailPanel = () => (
    <div style={isMobile ? theme.detailPanelMobile : theme.detailPanel}>
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
                {selected.wikilinks.map((link) => {
                  const exists = noteExists(link);
                  return (
                    <span
                      key={link}
                      style={exists ? theme.wikilink : theme.deadWikilink}
                      onClick={() => exists && handleSelect(`${link}.md`)}
                      title={exists ? link : `${link} (not yet created)`}
                    >
                      [[{link}]]
                    </span>
                  );
                })}
              </div>
            )}
          </div>
          <div style={theme.markdownBody}>
            <ReactMarkdown components={mdComponents}>
              {renderWikilinks(selected.content)}
            </ReactMarkdown>
          </div>
        </>
      ) : (
        <div style={{ padding: 32, opacity: 0.4, fontSize: 14 }}>
          Select a note to view its content
        </div>
      )}
    </div>
  );

  const renderChatPanel = () => (
    <div style={isMobile ? theme.chatPanelMobile : theme.chatPanel}>
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
              msg.role === "user" ? theme.chatUserMsg : theme.chatAssistantMsg
            }
          >
            {msg.role === "assistant" ? (
              <ReactMarkdown components={mdComponents}>
                {renderWikilinks(msg.content || "...")}
              </ReactMarkdown>
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
      <div style={theme.chatInputArea}>
        <textarea
          value={chatInput}
          onChange={(e) => {
            setChatInput(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleChatSend();
            }
          }}
          placeholder="Ask about your notes... (Shift+Enter for newline)"
          style={theme.chatInput}
          disabled={chatStreaming}
          rows={1}
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
  );

  // --- Mobile tab bar ---

  const renderMobileNav = () => (
    <div style={theme.mobileNav}>
      {(["list", "detail", "chat"] as MobileView[]).map((view) => (
        <button
          key={view}
          onClick={() => {
            setMobileView(view);
            if (view === "chat") setChatOpen(true);
          }}
          style={{
            ...theme.mobileNavButton,
            ...(mobileView === view ? theme.mobileNavButtonActive : {}),
          }}
        >
          {view === "list" ? "Notes" : view === "detail" ? "View" : "Chat"}
        </button>
      ))}
    </div>
  );

  // --- Layout ---

  return (
    <div
      className={dark ? "theme-dark" : "theme-light"}
      style={{
        ...theme.root,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}
    >
      {/* Header */}
      <header style={theme.header}>
        <h1 style={{ margin: 0, fontSize: isMobile ? 16 : 18 }}>
          Obsidian Knowledge
        </h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleToday} style={theme.headerButton}>
            Today
          </button>
          {!isMobile && (
            <button
              onClick={() => setChatOpen(!chatOpen)}
              style={theme.headerButton}
            >
              {chatOpen ? "Close Chat" : "Chat"}
            </button>
          )}
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
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSearch();
              if (isMobile) setMobileView("list");
            }
          }}
          placeholder="Search notes..."
          style={theme.searchInput}
        />
        <button
          onClick={() => {
            handleSearch();
            if (isMobile) setMobileView("list");
          }}
          style={theme.button}
        >
          Search
        </button>
      </div>

      {/* Main content */}
      {isMobile ? (
        // Mobile: single panel at a time
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {renderMobileNav()}
          {mobileView === "list" && <div style={{ flex: 1, overflow: "auto" }}>{renderListPanel()}</div>}
          {mobileView === "detail" && <div style={{ flex: 1, overflow: "auto" }}>{renderDetailPanel()}</div>}
          {mobileView === "chat" && renderChatPanel()}
        </div>
      ) : (
        // Desktop: multi-column
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {renderListPanel()}
          {renderDetailPanel()}
          {chatOpen && renderChatPanel()}
        </div>
      )}
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
      minWidth: 0,
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
      whiteSpace: "nowrap" as const,
    },
    // Desktop panels
    listPanel: {
      width: 280,
      minWidth: 280,
      borderRight: "1px solid #e0e0e0",
      overflowY: "auto" as const,
      background: "#fafafa",
    },
    detailPanel: {
      flex: 1,
      overflowY: "auto" as const,
      display: "flex" as const,
      flexDirection: "column" as const,
    },
    chatPanel: {
      width: 400,
      minWidth: 400,
      borderLeft: "1px solid #e0e0e0",
      display: "flex" as const,
      flexDirection: "column" as const,
      background: "#fafafa",
    },
    // Mobile panels
    listPanelMobile: {
      flex: 1,
      overflowY: "auto" as const,
      background: "#fafafa",
    },
    detailPanelMobile: {
      flex: 1,
      overflowY: "auto" as const,
      display: "flex" as const,
      flexDirection: "column" as const,
    },
    chatPanelMobile: {
      flex: 1,
      display: "flex" as const,
      flexDirection: "column" as const,
      background: "#fafafa",
    },
    // Mobile navigation
    mobileNav: {
      display: "flex" as const,
      borderBottom: "1px solid #e0e0e0",
      background: "#fafafa",
    },
    mobileNavButton: {
      flex: 1,
      padding: "10px 0",
      border: "none",
      background: "transparent",
      fontSize: 13,
      fontWeight: 500 as const,
      cursor: "pointer" as const,
      color: "#666",
    },
    mobileNavButtonActive: {
      color: "#7c3aed",
      borderBottom: "2px solid #7c3aed",
    },
    // Shared
    listItem: {
      padding: "10px 16px",
      borderBottom: "1px solid #eee",
      cursor: "pointer" as const,
    },
    listItemSelected: { background: "#ede9fe" },
    detailHeader: { padding: "16px 24px", borderBottom: "1px solid #e0e0e0" },
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
    deadWikilink: {
      fontSize: 11,
      padding: "2px 8px",
      borderRadius: 12,
      background: "#fee2e2",
      color: "#991b1b",
      cursor: "default" as const,
      opacity: 0.7,
      textDecoration: "line-through" as const,
    },
    markdownBody: {
      padding: "16px 24px",
      flex: 1,
      lineHeight: 1.7,
      fontSize: 15,
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
      minWidth: 0,
      resize: "none" as const,
      overflow: "hidden",
      lineHeight: 1.4,
      fontFamily: "inherit",
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
      minWidth: 0,
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
      whiteSpace: "nowrap" as const,
    },
    listPanel: {
      width: 280,
      minWidth: 280,
      borderRight: "1px solid #2a2a4a",
      overflowY: "auto" as const,
      background: "#16162a",
    },
    detailPanel: {
      flex: 1,
      overflowY: "auto" as const,
      display: "flex" as const,
      flexDirection: "column" as const,
    },
    chatPanel: {
      width: 400,
      minWidth: 400,
      borderLeft: "1px solid #2a2a4a",
      display: "flex" as const,
      flexDirection: "column" as const,
      background: "#16162a",
    },
    listPanelMobile: {
      flex: 1,
      overflowY: "auto" as const,
      background: "#16162a",
    },
    detailPanelMobile: {
      flex: 1,
      overflowY: "auto" as const,
      display: "flex" as const,
      flexDirection: "column" as const,
    },
    chatPanelMobile: {
      flex: 1,
      display: "flex" as const,
      flexDirection: "column" as const,
      background: "#16162a",
    },
    mobileNav: {
      display: "flex" as const,
      borderBottom: "1px solid #2a2a4a",
      background: "#16162a",
    },
    mobileNavButton: {
      flex: 1,
      padding: "10px 0",
      border: "none",
      background: "transparent",
      fontSize: 13,
      fontWeight: 500 as const,
      cursor: "pointer" as const,
      color: "#888",
    },
    mobileNavButtonActive: {
      color: "#a78bfa",
      borderBottom: "2px solid #a78bfa",
    },
    listItem: {
      padding: "10px 16px",
      borderBottom: "1px solid #2a2a4a",
      cursor: "pointer" as const,
    },
    listItemSelected: { background: "#2d1b69" },
    detailHeader: { padding: "16px 24px", borderBottom: "1px solid #2a2a4a" },
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
    deadWikilink: {
      fontSize: 11,
      padding: "2px 8px",
      borderRadius: 12,
      background: "#3b1111",
      color: "#fca5a5",
      cursor: "default" as const,
      opacity: 0.7,
      textDecoration: "line-through" as const,
    },
    markdownBody: {
      padding: "16px 24px",
      flex: 1,
      lineHeight: 1.7,
      fontSize: 15,
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
      minWidth: 0,
      resize: "none" as const,
      overflow: "hidden",
      lineHeight: 1.4,
      fontFamily: "inherit",
    },
  },
};
