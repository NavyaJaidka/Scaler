"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import BookingWidget from "@/components/BookingWidget";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  latency?: number;
  timestamp?: number;
}

interface GitHubRepo {
  name: string;
  description: string;
  primary_language: string;
  languages: string[];
  topics: string[];
  stars: number;
  forks: number;
  url: string;
  updated_at: string;
  commits: string[];
  summary: string;
}

interface VoiceConfig {
  enabled: boolean;
  phone_number: string;
  configured?: Record<string, boolean>;
}

const SUGGESTED_QUESTIONS = [
  "Why should Scaler hire you?",
  "What makes you unique?",
  "Tell me about your GitHub projects",
  "What's your tech stack?",
  "Check interview availability",
  "Call AI representative",
  "What AI/ML have you built?",
];

const INITIAL_MESSAGE: Message = {
  role: "assistant",
  content:
    "Hi! I'm the AI representative for [YOUR NAME] 👋\n\n" +
    "I can tell you about their background, skills, GitHub projects, and work experience — " +
    "all grounded in their real resume and repos. I can also book a call with them directly.\n\n" +
    "What would you like to know?",
  timestamp: Date.now(),
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showBooking, setShowBooking] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfig | null>(null);
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null);
  const [showProjects, setShowProjects] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "/api/backend";

  // Check backend health on mount
  useEffect(() => {
    fetch(`${BACKEND}/health`)
      .then(r => r.json())
      .then(d => setIsOnline(d.status === "ok"))
      .catch(() => setIsOnline(false));
  }, [BACKEND]);

  useEffect(() => {
    fetch(`${BACKEND}/github/repos`)
      .then(r => r.json())
      .then(d => {
        const fetchedRepos = d.repos || [];
        setRepos(fetchedRepos);
      })
      .catch(() => {
        setRepos([]);
      });
  }, [BACKEND]);

  useEffect(() => {
    fetch(`${BACKEND}/voice/config`)
      .then(r => r.json())
      .then(d => setVoiceConfig(d))
      .catch(() => setVoiceConfig(null));
  }, [BACKEND]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, showBooking]);

  const send = useCallback(async (query?: string) => {
    const text = (query ?? input).trim();
    if (!text || loading) return;
    const lowerText = text.toLowerCase();
    const isProjectQuestion =
      lowerText.includes("github") ||
      lowerText.includes("project") ||
      lowerText.includes("repo");
    setShowProjects(isProjectQuestion);
    if (!isProjectQuestion) setExpandedRepo(null);

    const userMsg: Message = {
      role: "user",
      content: text,
      timestamp: Date.now(),
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    setLoading(true);
    setShowBooking(false);

    try {
      const res = await fetch(`${BACKEND}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_history: messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      const body = await res.text();
      const data = body ? JSON.parse(body) : {};
      if (!res.ok) throw new Error(data.detail || body || `HTTP ${res.status}`);

      const assistantMsg: Message = {
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        latency: data.latency_ms,
        timestamp: Date.now(),
      };

      setMessages([...newHistory, assistantMsg]);

      if (data.booking_available) {
        setTimeout(() => setShowBooking(true), 400);
      }
    } catch (error) {
      console.error("Chat request failed:", error);
      const detail = error instanceof Error ? error.message : "Unknown error";
      setMessages([
        ...newHistory,
        {
          role: "assistant",
          content: `Sorry, the backend chat request failed: ${detail}`,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [input, loading, messages, BACKEND]);

  const startVoiceCall = () => {
    const phoneNumber = voiceConfig?.phone_number?.trim();
    if (phoneNumber) {
      window.location.href = `tel:${phoneNumber.replace(/[^\d+]/g, "")}`;
      return;
    }

    setShowProjects(false);
    setExpandedRepo(null);
    setMessages(current => [
      ...current,
      {
        role: "user",
        content: "Call AI representative",
        timestamp: Date.now(),
      },
      {
        role: "assistant",
        content:
          "Voice calling is almost ready, but the public Vapi phone number is not configured yet. Add VAPI_PHONE_NUMBER to your env after you connect the Vapi number, then restart the backend.",
        timestamp: Date.now(),
      },
    ]);
  };

  const handleSuggestedQuestion = (question: string) => {
    if (question.toLowerCase().includes("call ai representative")) {
      startVoiceCall();
      return;
    }

    const lower = question.toLowerCase();
    const isProjectQuestion =
      lower.includes("github") ||
      lower.includes("project") ||
      lower.includes("repo");
    setShowProjects(isProjectQuestion);
    if (!isProjectQuestion) setExpandedRepo(null);
    send(question);
  };

  const toggleRepo = (repoName: string) => {
    setExpandedRepo(current => (current === repoName ? null : repoName));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const formatContent = (content: string) => {
    return content.split("\n").map((line, i) => (
      <span key={i}>
        {line}
        {i < content.split("\n").length - 1 && <br />}
      </span>
    ));
  };

  const sourceLabel = (src: string) => {
    if (src === "resume") return { label: "Resume", cls: "source-resume" };
    if (src === "github") return { label: "GitHub", cls: "source-github" };
    return { label: src, cls: "bg-gray-100 text-gray-600" };
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      {/* Background decoration */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500 opacity-5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-purple-500 opacity-5 rounded-full blur-3xl" />
      </div>

      {/* Chat container */}
      <div className="glass-card w-full max-w-2xl rounded-2xl flex flex-col h-[90vh] max-h-[700px] relative z-10">

        {/* Header */}
        <div className="bg-gradient-to-r from-blue-700 to-blue-600 p-4 rounded-t-2xl text-white flex-shrink-0">
          <div className="flex items-center gap-3">
            {/* Avatar */}
            <div className="w-10 h-10 rounded-full bg-white/20 border border-white/30 flex items-center justify-center font-bold text-sm flex-shrink-0">
              AI
            </div>

            {/* Identity */}
            <div className="flex-1 min-w-0">
              <h1 className="text-base font-bold leading-tight">[YOUR NAME]</h1>
              <p className="text-[11px] opacity-70 leading-tight mt-0.5">
                AI Representative · RAG-grounded · Gemini 2.5 Flash
              </p>
            </div>

            {/* Status */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <div className={`w-2 h-2 rounded-full ${isOnline ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
              <span className="text-[11px] opacity-75">{isOnline ? "Online" : "Offline"}</span>
            </div>
          </div>

          {/* Tech stack badges */}
          <div className="flex gap-1.5 mt-3 flex-wrap">
            {["Gemini 2.5 Flash", "OpenAI Embeddings", "Pinecone RAG", "Cal.com"].map(tag => (
              <span key={tag}
                className="text-[10px] px-2 py-0.5 rounded-full bg-white/15 border border-white/20 font-medium">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Quick-question chips */}
        <div className="px-3 py-2 border-b border-gray-100 flex gap-1.5 overflow-x-auto flex-shrink-0 scrollbar-hide">
          {SUGGESTED_QUESTIONS.map(q => (
            <button
              key={q}
              onClick={() => handleSuggestedQuestion(q)}
              disabled={loading}
              className="text-[11px] whitespace-nowrap px-3 py-1.5 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors disabled:opacity-50 font-medium flex-shrink-0"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} ${msg.role === "user" ? "msg-user" : "msg-assistant"}`}>
              <div className={`max-w-[82%] ${msg.role === "user" ? "" : "w-full"}`}>
                {/* Bubble */}
                <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-100"
                }`}>
                  {formatContent(msg.content)}
                </div>

                {/* Source tags + latency */}
                {msg.role === "assistant" && (msg.sources?.length || msg.latency) ? (
                  <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    {msg.sources?.map(src => {
                      const { label, cls } = sourceLabel(src);
                      return (
                        <span key={src} className={`source-tag ${cls}`}>{label}</span>
                      );
                    })}
                    {msg.latency && (
                      <span className="text-[10px] text-gray-400">{msg.latency}ms</span>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          ))}

          {showProjects && (
            <div className="msg-assistant">
              <div className="w-full rounded-2xl rounded-bl-sm border border-gray-100 bg-gray-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <p className="text-sm font-semibold text-gray-900">GitHub projects</p>
                  <span className="text-[10px] text-gray-400">{repos.length} repos</span>
                </div>

                {repos.length === 0 ? (
                  <p className="text-sm text-gray-600">
                    No GitHub repos are loaded yet. Run <span className="font-mono">python scripts/fetch_github.py</span>.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {repos.map((repo, index) => {
                      const isOpen = expandedRepo === repo.name;
                      return (
                        <div key={repo.name} className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                          <button
                            onClick={() => toggleRepo(repo.name)}
                            className="w-full flex items-center justify-between gap-3 px-3 py-2 text-left hover:bg-blue-50 transition-colors"
                          >
                            <span className="flex items-center gap-2 min-w-0">
                              <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[11px] font-bold flex items-center justify-center flex-shrink-0">
                                {index + 1}
                              </span>
                              <span className="text-sm font-semibold text-gray-800 truncate">{repo.name}</span>
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 flex-shrink-0">
                                {repo.primary_language}
                              </span>
                            </span>
                            <span className="text-gray-400 text-sm">{isOpen ? "−" : "+"}</span>
                          </button>

                          {isOpen && (
                            <div className="px-3 pb-3 pt-1 border-t border-gray-100">
                              <p className="text-xs text-gray-700 leading-relaxed">
                                {repo.description || repo.summary || "No README summary available yet."}
                              </p>

                              {repo.languages.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-2">
                                  {repo.languages.slice(0, 10).map(language => (
                                    <span
                                      key={language}
                                      className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100"
                                    >
                                      {language}
                                    </span>
                                  ))}
                                </div>
                              )}

                              {repo.commits.length > 0 && (
                                <div className="mt-2">
                                  <p className="text-[10px] font-semibold text-gray-500 mb-1">Recent commits</p>
                                  <ul className="space-y-1">
                                    {repo.commits.slice(0, 3).map(commit => (
                                      <li key={commit} className="text-[11px] text-gray-500 truncate">
                                        {commit}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {repo.url && (
                                <a
                                  href={repo.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex mt-2 text-[11px] text-blue-600 hover:text-blue-700 font-semibold"
                                >
                                  Open GitHub repo
                                </a>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Typing indicator */}
          {loading && (
            <div className="flex justify-start msg-assistant">
              <div className="bg-gray-50 border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1.5 items-center h-4">
                  <div className="typing-dot w-2 h-2 rounded-full bg-gray-400" />
                  <div className="typing-dot w-2 h-2 rounded-full bg-gray-400" />
                  <div className="typing-dot w-2 h-2 rounded-full bg-gray-400" />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Booking widget */}
        {showBooking && (
          <div className="border-t border-blue-100 bg-gradient-to-b from-blue-50 to-white px-4 pt-3 pb-2 flex-shrink-0">
            <BookingWidget onClose={() => setShowBooking(false)} />
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-gray-100 p-3 flex gap-2 items-end flex-shrink-0 rounded-b-2xl">
          <input
            ref={inputRef}
            className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent placeholder:text-gray-400 transition-all resize-none"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about skills, projects, repos, availability…"
            disabled={loading}
            autoComplete="off"
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 w-10 h-10 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl flex items-center justify-center transition-colors"
            aria-label="Send message"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </main>
  );
}
