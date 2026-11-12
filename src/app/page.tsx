"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  MessageSquare,
  Clock,
  Plus,
  Send,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Globe,
  Copy,
  Check,
} from "lucide-react";

interface Citation {
  index: number;
  title: string;
  url: string;
  snippet?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  citations?: Citation[];
  search_queries?: string[];
}

interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [timezone, setTimezone] = useState<string>("UTC");
  const [copiedSessionId, setCopiedSessionId] = useState<boolean>(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Detect local timezone on mount
  useEffect(() => {
    try {
      const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (detected) setTimezone(detected);
    } catch {
      setTimezone("UTC");
    }
    loadSessions();
  }, []);

  // Scroll to bottom on message updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusMessage]);

  const loadSessions = async () => {
    try {
      const res = await fetch("/api/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch {
      // Offline fallback
    }
  };

  const startNewChat = () => {
    const newId = crypto.randomUUID();
    setCurrentSessionId(newId);
    setMessages([]);
    setStatusMessage(null);
  };

  const selectSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setStatusMessage(null);
    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (err) {
      console.error("Failed to load session messages", err);
    }
  };

  const copySessionId = () => {
    if (!currentSessionId) return;
    navigator.clipboard.writeText(currentSessionId);
    setCopiedSessionId(true);
    setTimeout(() => setCopiedSessionId(false), 2000);
  };

  const sendMessage = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isStreaming) return;

    let sessId = currentSessionId;
    if (!sessId) {
      sessId = crypto.randomUUID();
      setCurrentSessionId(sessId);
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);
    setStatusMessage("Analyzing query & temporal context...");

    // Create placeholder assistant message
    const assistantMsgId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      citations: [],
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversationId: sessId,
          message: text,
          timezone,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body readable stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const evtBlock of events) {
          const lines = evtBlock.split("\n");
          let eventType = "";
          let dataStr = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              dataStr = line.slice(6).trim();
            }
          }

          if (eventType && dataStr) {
            try {
              const data = JSON.parse(dataStr);

              if (eventType === "status") {
                setStatusMessage(data.message || null);
              } else if (eventType === "token") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, content: m.content + data }
                      : m
                  )
                );
              } else if (eventType === "citation") {
                setMessages((prev) =>
                  prev.map((m) => {
                    if (m.id !== assistantMsgId) return m;
                    const existing = m.citations || [];
                    if (existing.some((c) => c.url === data.url)) return m;
                    return { ...m, citations: [...existing, data] };
                  })
                );
              } else if (eventType === "done") {
                if (data.citations) {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMsgId
                        ? { ...m, citations: data.citations }
                        : m
                    )
                  );
                }
                setStatusMessage(null);
                loadSessions();
              } else if (eventType === "error") {
                setStatusMessage(`Error: ${data.error}`);
              }
            } catch {
              // Parse error
            }
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusMessage(`Failed: ${msg}`);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar: Conversation Sessions */}
      <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col hidden md:flex">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
              M
            </div>
            <div>
              <h1 className="font-semibold text-sm tracking-wide text-white">Minimi</h1>
              <p className="text-xs text-slate-400">Search & Temporal Agent</p>
            </div>
          </div>
          <button
            onClick={startNewChat}
            className="p-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition text-xs flex items-center space-x-1"
            title="Start New Chat"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Sessions list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider px-2 py-1">
            Historical Sessions
          </div>
          {sessions.length === 0 ? (
            <div className="text-xs text-slate-500 px-2 py-4">No past sessions yet.</div>
          ) : (
            sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => selectSession(s.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition flex items-center justify-between ${
                  currentSessionId === s.id
                    ? "bg-indigo-950/60 text-indigo-200 border border-indigo-800/50"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`}
              >
                <div className="flex items-center space-x-2 truncate">
                  <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-70" />
                  <span className="truncate">{s.title || `Session ${s.id.slice(0, 8)}`}</span>
                </div>
                <ChevronRight className="w-3 h-3 opacity-40 shrink-0" />
              </button>
            ))
          )}
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-slate-800/80 bg-slate-900/60 text-[11px] text-slate-400 space-y-1">
          <div className="flex items-center justify-between">
            <span className="flex items-center space-x-1">
              <Globe className="w-3 h-3 text-slate-500" />
              <span>Timezone:</span>
            </span>
            <span className="text-slate-300 font-mono">{timezone}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center space-x-1">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              <span>Tool Limit:</span>
            </span>
            <span className="text-emerald-400 font-medium">1 (web_search)</span>
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-full bg-slate-950">
        {/* Top Navbar */}
        <header className="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/50 backdrop-blur-sm">
          <div className="flex items-center space-x-3">
            <span className="text-sm font-medium text-slate-200">
              {currentSessionId ? `Session: ${currentSessionId.slice(0, 8)}...` : "New Session"}
            </span>
            {currentSessionId && (
              <button
                onClick={copySessionId}
                className="text-xs text-slate-400 hover:text-slate-200 flex items-center space-x-1 bg-slate-800 px-2 py-0.5 rounded transition"
              >
                {copiedSessionId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedSessionId ? "Copied" : "Copy ID"}</span>
              </button>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <div className="px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 text-xs flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Model-Callable Tool: <strong>web_search</strong></span>
            </div>
          </div>
        </header>

        {/* Message View */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="max-w-2xl mx-auto mt-16 text-center space-y-6">
              <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 flex items-center justify-center mx-auto">
                <Search className="w-6 h-6" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-white">Ask Minimi Anything</h2>
                <p className="text-sm text-slate-400 max-w-md mx-auto">
                  Equipped with live web search, chronological memory, and cross-session question recall.
                </p>
              </div>

              {/* Quick Scenario Pills */}
              <div className="grid grid-cols-1 gap-2.5 text-left max-w-xl mx-auto pt-4">
                <button
                  onClick={() =>
                    sendMessage(
                      "On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing or shipped something big since?"
                    )
                  }
                  className="p-3 rounded-xl bg-slate-900 hover:bg-slate-800/80 border border-slate-800 text-xs text-slate-300 transition space-y-1 group"
                >
                  <div className="font-semibold text-indigo-300 flex items-center justify-between">
                    <span>Scenario A: CRM Shortlist & Changes</span>
                    <ChevronRight className="w-3.5 h-3.5 opacity-60 group-hover:translate-x-0.5 transition" />
                  </div>
                  <p className="text-slate-400 text-[11px]">
                    "On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing or shipped something big since?"
                  </p>
                </button>

                <button
                  onClick={() =>
                    sendMessage("What did I ask you on 3 November? Is your answer still correct today?")
                  }
                  className="p-3 rounded-xl bg-slate-900 hover:bg-slate-800/80 border border-slate-800 text-xs text-slate-300 transition space-y-1 group"
                >
                  <div className="font-semibold text-indigo-300 flex items-center justify-between">
                    <span>Scenario B: Historical Date Verification</span>
                    <ChevronRight className="w-3.5 h-3.5 opacity-60 group-hover:translate-x-0.5 transition" />
                  </div>
                  <p className="text-slate-400 text-[11px]">
                    "What did I ask you on 3 November? Is your answer still correct today?"
                  </p>
                </button>

                <button
                  onClick={() =>
                    sendMessage(
                      "Last Tuesday I asked you about Postgres hosting. Has any pricing changed since then?"
                    )
                  }
                  className="p-3 rounded-xl bg-slate-900 hover:bg-slate-800/80 border border-slate-800 text-xs text-slate-300 transition space-y-1 group"
                >
                  <div className="font-semibold text-indigo-300 flex items-center justify-between">
                    <span>Scenario C: Relative Weekday & Hosting Pricing</span>
                    <ChevronRight className="w-3.5 h-3.5 opacity-60 group-hover:translate-x-0.5 transition" />
                  </div>
                  <p className="text-slate-400 text-[11px]">
                    "Last Tuesday I asked you about Postgres hosting. Has any pricing changed since then?"
                  </p>
                </button>
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white rounded-br-none shadow-md"
                      : "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none shadow-sm"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{m.content || (isStreaming && "...")}</div>

                  {/* Inline Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-1.5">
                      <div className="text-[11px] font-semibold text-slate-400 flex items-center space-x-1">
                        <Search className="w-3 h-3 text-indigo-400" />
                        <span>Verified Sources & Citations:</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {m.citations.map((c) => (
                          <button
                            key={c.url}
                            onClick={() => setActiveCitation(c)}
                            className="text-[11px] bg-slate-800 hover:bg-slate-700 text-indigo-300 px-2 py-0.5 rounded border border-slate-700 flex items-center space-x-1 transition"
                          >
                            <span>[{c.index}]</span>
                            <span className="max-w-[140px] truncate">{c.title}</span>
                            <ExternalLink className="w-2.5 h-2.5 opacity-70" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {m.timestamp && (
                  <span className="text-[10px] text-slate-500 mt-1 px-1">
                    {new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
            ))
          )}

          {/* Status / Activity Indicator */}
          {statusMessage && (
            <div className="flex items-center space-x-2 text-xs text-indigo-400 bg-indigo-950/40 border border-indigo-900/50 rounded-lg px-3 py-2 w-fit animate-pulse">
              <Search className="w-3.5 h-3.5 animate-spin" />
              <span>{statusMessage}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <footer className="p-4 border-t border-slate-800 bg-slate-900/40">
          <div className="max-w-3xl mx-auto flex items-center space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything, query past days, or search recent updates..."
              disabled={isStreaming}
              className="flex-1 bg-slate-900 border border-slate-800 focus:border-indigo-500 focus:outline-none rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 transition"
            />
            <button
              onClick={() => sendMessage()}
              disabled={isStreaming || !input.trim()}
              className="p-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:hover:bg-indigo-600 text-white transition shadow-md shadow-indigo-600/20"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </footer>
      </main>

      {/* Citation Preview Modal */}
      {activeCitation && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-indigo-400">
                  Citation [{activeCitation.index}]
                </span>
                <h3 className="font-semibold text-white text-base leading-snug">
                  {activeCitation.title}
                </h3>
              </div>
              <button
                onClick={() => setActiveCitation(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800/80 leading-relaxed">
              "{activeCitation.snippet}"
            </p>

            <div className="flex items-center justify-between pt-2">
              <a
                href={activeCitation.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 underline"
              >
                <span>Visit Source URL</span>
                <ExternalLink className="w-3 h-3" />
              </a>
              <button
                onClick={() => setActiveCitation(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
