import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

declare const __API_PREFIX__: string;
const API = `${__API_PREFIX__}/api/notes/`;
const CHAT_API = `${__API_PREFIX__}/api/chat/`;
const VAULTS_API = `${__API_PREFIX__}/api/vaults/`;

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

  const [vaults, setVaults] = useState<Record<string, { name: string; default?: boolean }>>({});
  const [currentVault, setCurrentVault] = useState<string>("AgentKnowledge");
  const [existingNotes, setExistingNotes] = useState<Set<string>>(new Set());

  const [showInfo, setShowInfo] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsSection, setSettingsSection] = useState<string>("vaults");
  const [remoteVaults, setRemoteVaults] = useState<any[]>([]);
  const [editingVault, setEditingVault] = useState<string | null>(null);
  const [vaultActionStatus, setVaultActionStatus] = useState<Record<string, string>>({});
  const [setupVault, setSetupVault] = useState<any | null>(null);
  const [setupForm, setSetupForm] = useState({ localPath: "", password: "", vaultId: "", esIndex: "", readOnly: false });
  const [setupStatus, setSetupStatus] = useState<string>("");
  const [chatOpen, setChatOpen] = useState(window.innerWidth >= 768);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatModel, setChatModel] = useState("claude-haiku-4-5-20251001");
  const [chatStreaming, setChatStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);

  const isMobile = useIsMobile();

  const vaultParam = (extra?: Record<string, string>) => {
    const params = new URLSearchParams({ vault: currentVault, ...extra });
    return `?${params}`;
  };

  const refreshNoteList = () => {
    fetch(`${API}list/${vaultParam()}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.notes && setExistingNotes(new Set(d.notes)))
      .catch(() => {});
  };

  // Fetch vaults on mount
  useEffect(() => {
    fetch(VAULTS_API)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.vaults) {
          setVaults(d.vaults);
          const def = Object.entries(d.vaults).find(
            ([, v]: [string, any]) => v.default,
          );
          if (def) setCurrentVault(def[0]);
        }
      })
      .catch(() => {});
  }, []);

  // Load notes when vault changes
  useEffect(() => {
    setSelected(null);
    setResults([]);
    fetch(`${API}recent/${vaultParam({ size: "20" })}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.results && setResults(d.results))
      .catch(() => {});
    refreshNoteList();
  }, [currentVault]);

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
      const resp = await fetch(`${API}recent/${vaultParam({ size: "20" })}`);
      const data = await resp.json();
      if (data?.results) setResults(data.results);
      return;
    }
    const endpoint = `${API}semantic-search/${vaultParam()}`;
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, size: 20 }),
    });
    const data = await resp.json();
    if (data?.results) setResults(data.results);
  };

  const handleSelect = async (path: string) => {
    const resp = await fetch(`${API}${path.split("/").map(encodeURIComponent).join("/")}${vaultParam()}`);
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
          vault: currentVault,
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
              fetch(`${API}recent/${vaultParam({ size: "20" })}`)
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
    setTimeout(() => chatInputRef.current?.focus(), 0);
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
    const v = vaults[currentVault] as any;
    const fmt = v?.daily_note_format;
    if (!fmt) return;
    const now = new Date();
    const yyyy = String(now.getFullYear());
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const dd = String(now.getDate()).padStart(2, "0");
    const dateStr = `${yyyy}-${mm}-${dd}`;
    const path = fmt.replace("{YYYY}", yyyy).replace("{MM}", mm).replace("{DD}", dd);

    // Try to read it first
    const resp = await fetch(`${API}${path.split("/").map(encodeURIComponent).join("/")}${vaultParam()}`);
    if (resp.ok) {
      setSelected(await resp.json());
      if (isMobile) setMobileView("detail");
      return;
    }

    // Create it
    const dayName = now.toLocaleDateString("en-US", { weekday: "long" });
    await fetch(`${API}${vaultParam()}`, {
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
    const readResp = await fetch(`${API}${path.split("/").map(encodeURIComponent).join("/")}${vaultParam()}`);
    if (readResp.ok) {
      setSelected(await readResp.json());
      if (isMobile) setMobileView("detail");
    }

    // Refresh the list
    fetch(`${API}recent/${vaultParam({ size: "20" })}`)
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
          ref={chatInputRef}
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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h1 style={{ margin: 0, fontSize: isMobile ? 16 : 18 }}>
            Obsidian Knowledge
          </h1>
          {Object.keys(vaults).length > 1 && (
            <select
              value={currentVault}
              onChange={(e) => setCurrentVault(e.target.value)}
              style={{ ...theme.select, fontSize: 12, padding: "4px 8px" }}
            >
              {Object.entries(vaults).map(([id, v]: [string, any]) => (
                <option key={id} value={id}>{v.name}</option>
              ))}
            </select>
          )}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {(vaults[currentVault] as any)?.daily_note_format && (
            <button onClick={handleToday} style={theme.iconButton} title="Today's observations">
              📅
            </button>
          )}
          <button onClick={() => setShowSettings(true)} style={theme.iconButton} title="Settings">
            ⚙️
          </button>
          <button onClick={() => setShowInfo(true)} style={theme.iconButton} title="Connection info">
            ℹ️
          </button>
          {!isMobile && (
            <button
              onClick={() => setChatOpen(!chatOpen)}
              style={theme.iconButton}
              title={chatOpen ? "Close chat" : "Open chat"}
            >
              {chatOpen ? "✖️" : "💬"}
            </button>
          )}
          <button
            onClick={() => setDark(!dark)}
            style={theme.iconButton}
            title="Toggle theme"
          >
            {dark ? "☀️" : "🌙"}
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

      {/* Info modal */}
      {showInfo && (
        <div
          style={theme.modalOverlay}
          onClick={() => setShowInfo(false)}
        >
          <div
            style={theme.modal}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Connection Info</h2>
              <button onClick={() => setShowInfo(false)} style={theme.headerButton}>Close</button>
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.8 }}>
              <h3 style={{ marginTop: 0 }}>MCP Server</h3>
              <p>This knowledge base exposes an MCP (Model Context Protocol) server for agentic access.</p>
              <p><strong>Endpoint:</strong></p>
              <code style={theme.codeBlock}>{window.location.origin}{__API_PREFIX__}/mcp/</code>

              <h3>Authentication</h3>
              <p>The MCP endpoint requires a Bearer token. Include it in requests as:</p>
              <code style={theme.codeBlock}>Authorization: Bearer &lt;MCP_API_KEY&gt;</code>
              <p style={{ fontSize: 12, opacity: 0.6 }}>Set <code>MCP_API_KEY</code> in the server's <code>.env</code> file.</p>

              <h3>Claude Desktop</h3>
              <p>Add via <strong>Settings &gt; Connectors</strong> with the endpoint URL and Bearer token.</p>

              <h3>Claude Code</h3>
              <code style={theme.codeBlock}>{`claude mcp add obsidian-knowledge --transport http ${window.location.origin}${__API_PREFIX__}/mcp/ --header "Authorization: Bearer <MCP_API_KEY>"`}</code>

              <h3>Available Tools</h3>
              <ul style={{ paddingLeft: 20 }}>
                <li><strong>search</strong> — full-text BM25 search</li>
                <li><strong>semantic</strong> — hybrid search (BM25 + vector)</li>
                <li><strong>read</strong> — read a note by path</li>
                <li><strong>list_all_notes</strong> — list notes by folder</li>
                <li><strong>create</strong> — create or update a note</li>
                <li><strong>delete</strong> — delete a note</li>
                <li><strong>reindex</strong> — resync vault to Elasticsearch</li>
              </ul>

              <h3>REST API</h3>
              <code style={theme.codeBlock}>{window.location.origin}{__API_PREFIX__}/api/notes/</code>
              <p style={{ fontSize: 12, opacity: 0.6 }}>Protected by HTTP Basic Auth when accessed through nginx.</p>
            </div>
          </div>
        </div>
      )}

      {/* Settings overlay */}
      {showSettings && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 1000,
          background: theme.root.background, color: theme.root.color,
          display: "flex", flexDirection: "column",
        }}>
          {/* Settings header */}
          <div style={{
            ...theme.header, display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <h2 style={{ margin: 0, fontSize: 18 }}>Settings</h2>
            <button onClick={() => { setShowSettings(false); setEditingVault(null); }} style={theme.headerButton}>
              Close
            </button>
          </div>

          <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
            {/* Left nav */}
            <div style={{
              width: isMobile ? "100%" : 200, minWidth: isMobile ? undefined : 200,
              borderRight: isMobile ? "none" : `1px solid ${dark ? "#2a2a4a" : "#e0e0e0"}`,
              padding: "8px 0",
              background: dark ? "#16162a" : "#fafafa",
              ...(isMobile && settingsSection ? { display: "none" } : {}),
            }}>
              {[{ id: "vaults", label: "Vaults" }].map((sec) => (
                <div
                  key={sec.id}
                  onClick={() => setSettingsSection(sec.id)}
                  style={{
                    padding: "10px 20px", cursor: "pointer", fontSize: 14, fontWeight: 500,
                    background: settingsSection === sec.id ? (dark ? "#2d1b69" : "#ede9fe") : "transparent",
                    borderLeft: settingsSection === sec.id ? "3px solid #7c3aed" : "3px solid transparent",
                  }}
                >
                  {sec.label}
                </div>
              ))}
            </div>

            {/* Settings content */}
            <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
              {settingsSection === "vaults" && (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <h3 style={{ margin: 0 }}>Configured Vaults</h3>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        onClick={async () => {
                          const resp = await fetch(`${VAULTS_API}remote/`);
                          if (resp.ok) {
                            const d = await resp.json();
                            setRemoteVaults(d.vaults || []);
                          }
                        }}
                        style={theme.button}
                      >
                        Browse Remote Vaults
                      </button>
                    </div>
                  </div>

                  {/* Vault table */}
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, marginBottom: 24 }}>
                    <thead>
                      <tr style={{ borderBottom: `2px solid ${dark ? "#2a2a4a" : "#e0e0e0"}`, textAlign: "left" }}>
                        <th style={{ padding: "8px 12px" }}>Name</th>
                        <th style={{ padding: "8px 12px" }}>ID</th>
                        <th style={{ padding: "8px 12px" }}>ES Index</th>
                        <th style={{ padding: "8px 12px" }}>Sync</th>
                        <th style={{ padding: "8px 12px" }}>Read-Only</th>
                        <th style={{ padding: "8px 12px" }}>Default</th>
                        <th style={{ padding: "8px 12px" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(vaults).map(([id, v]: [string, any]) => (
                        <tr key={id} style={{ borderBottom: `1px solid ${dark ? "#2a2a4a" : "#eee"}` }}>
                          <td style={{ padding: "8px 12px" }}>{v.name}</td>
                          <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 12 }}>{id}</td>
                          <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 12 }}>{v.es_index}</td>
                          <td style={{ padding: "8px 12px" }}>{v.sync_enabled ? "✓" : "✗"}</td>
                          <td style={{ padding: "8px 12px" }}>{v.read_only ? "🔒" : ""}</td>
                          <td style={{ padding: "8px 12px" }}>{v.default ? "★" : ""}</td>
                          <td style={{ padding: "8px 12px" }}>
                            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                              <button
                                onClick={async () => {
                                  setVaultActionStatus((s) => ({ ...s, [id]: "syncing..." }));
                                  const r = await fetch(`${VAULTS_API}${id}/sync/`, { method: "POST" });
                                  const d = await r.json();
                                  setVaultActionStatus((s) => ({ ...s, [id]: d.status === "ok" ? "synced" : "error" }));
                                  setTimeout(() => setVaultActionStatus((s) => ({ ...s, [id]: "" })), 3000);
                                }}
                                style={{ ...theme.headerButton, fontSize: 11, padding: "2px 8px" }}
                              >
                                Sync
                              </button>
                              <button
                                onClick={async () => {
                                  setVaultActionStatus((s) => ({ ...s, [id]: "reindexing..." }));
                                  const r = await fetch(`${VAULTS_API}${id}/reindex/`, { method: "POST" });
                                  const d = await r.json();
                                  setVaultActionStatus((s) => ({ ...s, [id]: `indexed: ${d.indexed}, skipped: ${d.skipped}` }));
                                  setTimeout(() => setVaultActionStatus((s) => ({ ...s, [id]: "" })), 5000);
                                }}
                                style={{ ...theme.headerButton, fontSize: 11, padding: "2px 8px" }}
                              >
                                Reindex
                              </button>
                              <button
                                onClick={() => setEditingVault(editingVault === id ? null : id)}
                                style={{ ...theme.headerButton, fontSize: 11, padding: "2px 8px" }}
                              >
                                Edit
                              </button>
                              {!v.default && (
                                <button
                                  onClick={async () => {
                                    if (confirm(`Remove vault "${v.name}"? (Files are not deleted)`)) {
                                      await fetch(`${VAULTS_API}${id}/`, { method: "DELETE" });
                                      const resp = await fetch(VAULTS_API);
                                      if (resp.ok) {
                                        const d = await resp.json();
                                        setVaults(d.vaults);
                                      }
                                    }
                                  }}
                                  style={{ ...theme.headerButton, fontSize: 11, padding: "2px 8px", color: "#ef4444" }}
                                >
                                  Remove
                                </button>
                              )}
                            </div>
                            {vaultActionStatus[id] && (
                              <div style={{ fontSize: 11, marginTop: 4, opacity: 0.7 }}>{vaultActionStatus[id]}</div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Edit vault form */}
                  {editingVault && vaults[editingVault] && (() => {
                    const v = vaults[editingVault] as any;
                    return (
                      <div style={{
                        padding: 16, marginBottom: 24,
                        border: `1px solid ${dark ? "#2a2a4a" : "#e0e0e0"}`,
                        borderRadius: 8, background: dark ? "#1e1e3a" : "#f9f9f9",
                      }}>
                        <h4 style={{ margin: "0 0 12px" }}>Edit: {editingVault}</h4>
                        <form onSubmit={async (e) => {
                          e.preventDefault();
                          const fd = new FormData(e.target as HTMLFormElement);
                          const config = {
                            name: fd.get("name") as string,
                            path: fd.get("path") as string,
                            sync_path: fd.get("sync_path") as string,
                            es_index: fd.get("es_index") as string,
                            default: fd.get("default") === "on",
                            sync_enabled: fd.get("sync_enabled") === "on",
                            read_only: fd.get("read_only") === "on",
                            daily_note_format: fd.get("daily_note_format") as string,
                            instructions: fd.get("instructions") as string,
                          };
                          await fetch(`${VAULTS_API}${editingVault}/`, {
                            method: "PUT",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(config),
                          });
                          setEditingVault(null);
                          const resp = await fetch(VAULTS_API);
                          if (resp.ok) setVaults((await resp.json()).vaults);
                        }}>
                          {[
                            { label: "Name", name: "name", value: v.name },
                            { label: "Path", name: "path", value: v.path },
                            { label: "Sync Path", name: "sync_path", value: v.sync_path },
                            { label: "ES Index", name: "es_index", value: v.es_index },
                          ].map((f) => (
                            <div key={f.name} style={{ marginBottom: 8 }}>
                              <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>{f.label}</label>
                              <input name={f.name} defaultValue={f.value} style={{ ...theme.searchInput, width: "100%" }} />
                            </div>
                          ))}
                          <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
                            <label style={{ fontSize: 13 }}>
                              <input type="checkbox" name="default" defaultChecked={v.default} /> Default
                            </label>
                            <label style={{ fontSize: 13 }}>
                              <input type="checkbox" name="read_only" defaultChecked={v.read_only} /> Read-Only
                            </label>
                            <label style={{ fontSize: 13 }}>
                              <input type="checkbox" name="sync_enabled" defaultChecked={v.sync_enabled} /> Sync Enabled
                            </label>
                          </div>
                          <div style={{ marginBottom: 8 }}>
                            <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Daily Note Format</label>
                            <input name="daily_note_format" defaultValue={v.daily_note_format || ""} placeholder="Observations/{YYYY}-{MM}-{DD}-Daily.md" style={{ ...theme.searchInput, width: "100%" }} />
                          </div>
                          <div style={{ marginBottom: 8 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                              <label style={{ fontSize: 12 }}>Vault Instructions</label>
                              <button type="button" onClick={async () => {
                                if (!confirm("This will replace the current instructions with auto-generated content based on the vault's folder structure. Continue?")) return;
                                const resp = await fetch(`${VAULTS_API}${editingVault}/instructions/generate/`, { method: "POST" });
                                if (resp.ok) {
                                  const data = await resp.json();
                                  const ta = document.querySelector('textarea[name="instructions"]') as HTMLTextAreaElement;
                                  if (ta) ta.value = data.instructions;
                                  if (data.suggested_daily_note_format) {
                                    const inp = document.querySelector('input[name="daily_note_format"]') as HTMLInputElement;
                                    if (inp) inp.value = data.suggested_daily_note_format;
                                  }
                                }
                              }} style={{ ...theme.headerButton, fontSize: 11, padding: "2px 8px" }}>Re-generate Instructions</button>
                            </div>
                            <textarea name="instructions" defaultValue={v.instructions || ""} rows={10} style={{ ...theme.searchInput, width: "100%", minHeight: 200, fontFamily: "monospace", fontSize: 12, resize: "vertical" }} />
                          </div>
                          <div style={{ display: "flex", gap: 8 }}>
                            <button type="submit" style={theme.button}>Save</button>
                            <button type="button" onClick={() => setEditingVault(null)} style={theme.headerButton}>Cancel</button>
                          </div>
                        </form>
                      </div>
                    );
                  })()}

                  {/* Remote vaults browser */}
                  {remoteVaults.length > 0 && (
                    <div>
                      <h3 style={{ marginBottom: 12 }}>Remote Obsidian Vaults</h3>
                      <p style={{ fontSize: 13, opacity: 0.6, marginBottom: 12 }}>
                        These are vaults available in your Obsidian Sync account. Select one to set up local sync.
                      </p>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                        <thead>
                          <tr style={{ borderBottom: `2px solid ${dark ? "#2a2a4a" : "#e0e0e0"}`, textAlign: "left" }}>
                            <th style={{ padding: "8px 12px" }}>Name</th>
                            <th style={{ padding: "8px 12px" }}>Region</th>
                            <th style={{ padding: "8px 12px" }}>Status</th>
                            <th style={{ padding: "8px 12px" }}>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {remoteVaults.map((rv: any) => {
                            const alreadyConfigured = Object.values(vaults).some(
                              (v: any) => v.name === rv.name || v.name === rv.name.replace(/([A-Z])/g, " $1").trim()
                            );
                            return (
                              <tr key={rv.id} style={{ borderBottom: `1px solid ${dark ? "#2a2a4a" : "#eee"}` }}>
                                <td style={{ padding: "8px 12px" }}>{rv.name}</td>
                                <td style={{ padding: "8px 12px" }}>{rv.region}</td>
                                <td style={{ padding: "8px 12px" }}>
                                  {alreadyConfigured ? (
                                    <span style={{ color: "#22c55e" }}>Configured</span>
                                  ) : (
                                    <span style={{ opacity: 0.5 }}>Not configured</span>
                                  )}
                                </td>
                                <td style={{ padding: "8px 12px" }}>
                                  {!alreadyConfigured && (
                                    <button
                                      onClick={() => {
                                        const vaultId = rv.name.replace(/\s+/g, "");
                                        setSetupVault(rv);
                                        setSetupForm({
                                          localPath: `/home/dave/dev/obsidian-knowledge/vaults/${vaultId}`,
                                          password: "",
                                          vaultId,
                                          esIndex: `obsidian-knowledge-${vaultId.toLowerCase()}`,
                                        });
                                        setSetupStatus("");
                                      }}
                                      style={{ ...theme.headerButton, fontSize: 11, padding: "2px 8px" }}
                                    >
                                      Set Up
                                    </button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Setup vault dialog */}
                  {setupVault && (
                    <div style={{
                      padding: 20, marginTop: 16,
                      border: `2px solid #7c3aed`,
                      borderRadius: 8, background: dark ? "#1e1e3a" : "#f9f9f9",
                    }}>
                      <h4 style={{ margin: "0 0 4px" }}>Set Up Vault: {setupVault.name}</h4>
                      <p style={{ fontSize: 13, opacity: 0.6, margin: "0 0 16px" }}>
                        This will create the local directory, link it to the remote vault,
                        run an initial sync, and index into Elasticsearch.
                      </p>
                      <div style={{ marginBottom: 10 }}>
                        <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Vault ID</label>
                        <input
                          value={setupForm.vaultId}
                          onChange={(e) => setSetupForm({ ...setupForm, vaultId: e.target.value })}
                          style={{ ...theme.searchInput, width: "100%" }}
                        />
                      </div>
                      <div style={{ marginBottom: 10 }}>
                        <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Local Directory</label>
                        <input
                          value={setupForm.localPath}
                          onChange={(e) => setSetupForm({ ...setupForm, localPath: e.target.value })}
                          style={{ ...theme.searchInput, width: "100%" }}
                        />
                      </div>
                      <div style={{ marginBottom: 10 }}>
                        <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Encryption Password (e2ee)</label>
                        <input
                          type="password"
                          value={setupForm.password}
                          onChange={(e) => setSetupForm({ ...setupForm, password: e.target.value })}
                          placeholder="Enter the vault's encryption password"
                          style={{ ...theme.searchInput, width: "100%" }}
                        />
                      </div>
                      <div style={{ marginBottom: 16 }}>
                        <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>ES Index Name</label>
                        <input
                          value={setupForm.esIndex}
                          onChange={(e) => setSetupForm({ ...setupForm, esIndex: e.target.value })}
                          style={{ ...theme.searchInput, width: "100%" }}
                        />
                      </div>
                      <div style={{ marginBottom: 16 }}>
                        <label style={{ fontSize: 13 }}>
                          <input
                            type="checkbox"
                            checked={setupForm.readOnly}
                            onChange={(e) => setSetupForm({ ...setupForm, readOnly: e.target.checked })}
                          /> Read-Only (prevent writes from UI, API, and MCP — only Obsidian Sync can modify)
                        </label>
                      </div>
                      {setupStatus && (
                        <div style={{
                          padding: "8px 12px", marginBottom: 12, borderRadius: 6, fontSize: 13,
                          background: setupStatus.startsWith("Error") ? "#fef2f2" : (dark ? "#1a2e1a" : "#f0fdf4"),
                          color: setupStatus.startsWith("Error") ? "#dc2626" : "#16a34a",
                        }}>
                          {setupStatus}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          onClick={async () => {
                            if (!setupForm.password) {
                              setSetupStatus("Error: Encryption password is required");
                              return;
                            }
                            setSetupStatus("Linking to remote vault...");
                            try {
                              const resp = await fetch(`${VAULTS_API}setup/`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                  vault_id: setupForm.vaultId,
                                  name: setupVault.name,
                                  remote_vault_name: setupVault.name,
                                  local_path: setupForm.localPath,
                                  sync_path: setupForm.localPath,
                                  es_index: setupForm.esIndex,
                                  password: setupForm.password,
                                  read_only: setupForm.readOnly,
                                  create_remote: false,
                                }),
                              });
                              const d = await resp.json();
                              if (d.status === "started" && d.job_id) {
                                // Poll for progress
                                const pollInterval = setInterval(async () => {
                                  try {
                                    const sr = await fetch(`${VAULTS_API}setup/status/${d.job_id}/`);
                                    const s = await sr.json();
                                    const files = s.files_synced ? ` (${s.files_synced.toLocaleString()} files)` : "";
                                    setSetupStatus(`${s.step}${files}`);
                                    if (s.status === "completed") {
                                      clearInterval(pollInterval);
                                      const indexed = s.reindex?.indexed || 0;
                                      setSetupStatus(`Done! Indexed ${indexed} notes.`);
                                      const vr = await fetch(VAULTS_API);
                                      if (vr.ok) setVaults((await vr.json()).vaults);
                                      setTimeout(() => { setSetupVault(null); setSetupStatus(""); }, 3000);
                                    } else if (s.status === "error") {
                                      clearInterval(pollInterval);
                                      setSetupStatus(`Error: ${s.error}`);
                                    }
                                  } catch {
                                    // Polling failed, keep trying
                                  }
                                }, 2000);
                              } else if (d.status === "error") {
                                setSetupStatus(`Error at ${d.step || "unknown"}: ${d.stderr || d.stdout || JSON.stringify(d)}`);
                              }
                            } catch (e) {
                              setSetupStatus(`Error: ${e}`);
                            }
                          }}
                          style={theme.button}
                          disabled={setupStatus !== "" && !setupStatus.startsWith("Error")}
                        >
                          {setupStatus && !setupStatus.startsWith("Error") ? "Setting up..." : "Set Up Vault"}
                        </button>
                        <button
                          onClick={() => { setSetupVault(null); setSetupStatus(""); }}
                          style={theme.headerButton}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
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
    iconButton: {
      background: "#f0f0f0",
      border: "1px solid #ddd",
      borderRadius: 8,
      cursor: "pointer" as const,
      fontSize: 16,
      padding: "4px 8px",
      lineHeight: 1,
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
    modalOverlay: {
      position: "fixed" as const,
      top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.4)",
      display: "flex" as const,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      zIndex: 1000,
    },
    modal: {
      background: "#fff",
      color: "#1a1a1a",
      borderRadius: 12,
      padding: "24px",
      maxWidth: 560,
      width: "90%",
      maxHeight: "80vh",
      overflowY: "auto" as const,
      boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
    },
    codeBlock: {
      display: "block" as const,
      background: "#f3f4f6",
      border: "1px solid #e5e7eb",
      borderRadius: 6,
      padding: "8px 12px",
      fontSize: 12,
      fontFamily: "monospace",
      overflowX: "auto" as const,
      marginBottom: 8,
      wordBreak: "break-all" as const,
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
    iconButton: {
      background: "#2a2a4a",
      border: "1px solid #3a3a5a",
      borderRadius: 8,
      cursor: "pointer" as const,
      fontSize: 16,
      padding: "4px 8px",
      lineHeight: 1,
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
    modalOverlay: {
      position: "fixed" as const,
      top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.6)",
      display: "flex" as const,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      zIndex: 1000,
    },
    modal: {
      background: "#1a1a2e",
      color: "#e0e0e0",
      borderRadius: 12,
      padding: "24px",
      maxWidth: 560,
      width: "90%",
      maxHeight: "80vh",
      overflowY: "auto" as const,
      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      border: "1px solid #2a2a4a",
    },
    codeBlock: {
      display: "block" as const,
      background: "#1e1e3a",
      border: "1px solid #2a2a4a",
      borderRadius: 6,
      padding: "8px 12px",
      fontSize: 12,
      fontFamily: "monospace",
      overflowX: "auto" as const,
      marginBottom: 8,
      wordBreak: "break-all" as const,
    },
  },
};
