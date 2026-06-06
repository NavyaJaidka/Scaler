"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import BookingWidget from "@/components/BookingWidget";
import VoiceCallWidget from "@/components/VoiceCallWidget";
import { backendPath } from "@/lib/backend";

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
  provider?: string;
  stream_url?: string;
  configured?: Record<string, boolean>;
}

const DRIVE_FILE_ID = "1VbdBsU-kOoa5UrJZ9fY6VpRZWXXh5CTt";
const GITHUB_PROFILE_URL = "https://github.com/NavyaJaidka";
const RESUME_DOWNLOAD_URL = `https://drive.google.com/uc?export=download&id=${DRIVE_FILE_ID}`;

const QUICK_ACTIONS = [
  { label: "Why should Scaler hire you?", type: "question" },
  { label: "What makes you unique?", type: "question" },
  { label: "Tell me about your GitHub projects", type: "question" },
  { label: "What's your tech stack?", type: "question" },
  { label: "Check interview availability", type: "question" },
  { label: "Call AI representative", type: "voice" },
  { label: "What AI/ML have you built?", type: "question" },
  { label: "GitHub profile", type: "github" },
  { label: "Download resume", type: "resume" },
];

const INITIAL_MESSAGE: Message = {
  role: "assistant",
  content:
    "Hi! I'm the AI representative for Navya Jaidka 👋\n\n" +
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
  const [showVoiceCall, setShowVoiceCall] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfig | null>(null);
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null);
  const [showProjects, setShowProjects] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Theme initialization
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const shouldBeDark = savedTheme ? savedTheme === "dark" : prefersDark;
    setIsDark(shouldBeDark);
    if (shouldBeDark) {
      document.documentElement.classList.add("dark");
    }
  }, []);

  const toggleTheme = () => {
    setIsDark(!isDark);
    if (!isDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  // Check backend health on mount
  useEffect(() => {
    fetch(backendPath("/health"))
      .then(r => r.json())
      .then(d => setIsOnline(d.status === "ok"))
      .catch(() => setIsOnline(false));
  }, []);

  useEffect(() => {
    fetch(backendPath("/github/repos"))
      .then(r => r.json())
      .then(d => {
        const fetchedRepos = d.repos || [];
        setRepos(fetchedRepos);
      })
      .catch(() => {
        setRepos([]);
      });
  }, []);

  useEffect(() => {
    fetch(backendPath("/voice/config"))
      .then(r => r.json())
      .then(d => setVoiceConfig(d))
      .catch(() => setVoiceConfig(null));
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, showBooking, showVoiceCall]);

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
      const res = await fetch(backendPath("/chat"), {
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
  }, [input, loading, messages]);

  const startVoiceCall = () => {
    setShowProjects(false);
    setExpandedRepo(null);
    setShowBooking(false);
    setShowVoiceCall(true);
  };

  const handleQuickAction = (action: typeof QUICK_ACTIONS[number]) => {
    if (action.type === "github") {
      window.open(GITHUB_PROFILE_URL, "_blank", "noopener,noreferrer");
      return;
    }

    if (action.type === "resume") {
      window.open(RESUME_DOWNLOAD_URL, "_blank", "noopener,noreferrer");
      return;
    }

    if (action.type === "voice") {
      startVoiceCall();
      return;
    }

    const lower = action.label.toLowerCase();
    const isProjectQuestion =
      lower.includes("github") ||
      lower.includes("project") ||
      lower.includes("repo");
    setShowProjects(isProjectQuestion);
    if (!isProjectQuestion) setExpandedRepo(null);
    send(action.label);
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
    if (src === "resume") return { label: "Resume", cls: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-800" };
    if (src === "github") return { label: "GitHub", cls: "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-300 dark:border-purple-800" };
    return { label: src, cls: "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600" };
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 transition-colors duration-300">
      {/* Background decoration */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500 opacity-8 rounded-full blur-3xl dark:opacity-5" />
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-purple-500 opacity-8 rounded-full blur-3xl dark:opacity-5" />
      </div>

      {/* Chat container */}
      <div className="w-full max-w-2xl rounded-3xl flex flex-col h-[90vh] max-h-[700px] relative z-10 bg-white dark:bg-slate-800 shadow-2xl dark:shadow-2xl dark:shadow-black/50 overflow-hidden transition-colors duration-300">

        {/* Header */}
        <div className="bg-gradient-to-r from-blue-700 to-blue-600 dark:from-blue-900 dark:to-blue-800 px-6 py-5 text-white flex-shrink-0 transition-colors duration-300">
          <div className="flex items-center gap-4">
            {/* Avatar */}
            <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center font-bold text-base flex-shrink-0 shadow-lg">
              AI
            </div>

            {/* Identity */}
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-bold leading-tight">Navya Jaidka</h1>
              <p className="text-xs opacity-80 leading-snug mt-1 font-medium">
                AI Representative · RAG-grounded · Gemini 2.5 Flash
              </p>
            </div>

            {/* Status */}
            <div className="flex items-center gap-2 flex-shrink-0 px-3 py-1.5 bg-white/10 backdrop-blur-md rounded-full border border-white/20">
              <div className={`w-2 h-2 rounded-full ${isOnline ? "bg-emerald-300 animate-pulse" : "bg-red-300"}`} />
              <span className="text-xs font-medium opacity-90">{isOnline ? "Online" : "Offline"}</span>
            </div>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="flex-shrink-0 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20 flex items-center justify-center transition-all hover:scale-110"
              aria-label="Toggle dark mode"
            >
              {isDark ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1hm4.22 1.78a1 1 0 011.414 0l.707.707a1 1 0 11-1.414 1.414l-.707-.707a1 1 0 010-1.414zm2.828 2.828a1 1 0 011.414 0l.707.707a1 1 0 11-1.414 1.414l-.707-.707a1 1 0 010-1.414zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm-4.22-1.78a1 1 0 011.414 0l.707.707a1 1 0 11-1.414 1.414l-.707-.707a1 1 0 010-1.414zm-2.828-2.828a1 1 0 011.414 0l.707.707a1 1 0 11-1.414 1.414l-.707-.707a1 1 0 010-1.414zM3 11a1 1 0 100-2H2a1 1 0 100 2h1zm14.22-9.22a1 1 0 011.414 0l.707.707a1 1 0 11-1.414 1.414l-.707-.707a1 1 0 010-1.414zM10 7a3 3 0 100 6 3 3 0 000-6z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          </div>

          {/* Tech stack badges */}
          <div className="flex gap-2 mt-4 flex-wrap">
            {["Gemini 2.5 Flash", "OpenAI Embeddings", "Pinecone RAG", "Cal.com"].map(tag => (
              <span key={tag}
                className="text-xs px-3 py-1.5 rounded-full bg-white/15 backdrop-blur-md border border-white/20 font-semibold hover:bg-white/20 transition-colors">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Quick-question chips */}
        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 flex gap-2 overflow-x-auto flex-shrink-0 scrollbar-hide bg-gradient-to-r from-slate-50 to-blue-50/30 dark:from-slate-700 dark:to-slate-700/50 transition-colors duration-300">
          {QUICK_ACTIONS.map(action => (
            <button
              key={action.label}
              onClick={() => handleQuickAction(action)}
              disabled={loading}
              className="text-xs whitespace-nowrap px-3.5 py-2 rounded-lg bg-gradient-to-r from-blue-50 to-blue-50 dark:from-blue-900 dark:to-blue-800 text-blue-700 dark:text-blue-200 hover:from-blue-100 hover:to-blue-100 dark:hover:from-blue-800 dark:hover:to-blue-700 border border-blue-200 dark:border-blue-700 transition-all disabled:opacity-50 font-semibold flex-shrink-0 shadow-sm hover:shadow-md hover:scale-105"
            >
              {action.label}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 bg-gradient-to-b from-white to-slate-50/50 dark:from-slate-800 dark:to-slate-800/50 transition-colors duration-300">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} ${msg.role === "user" ? "msg-user" : "msg-assistant"} animate-fadeIn`}>
              <div className={`max-w-[82%] ${msg.role === "user" ? "" : "w-full"}`}>
                {/* Bubble */}
                <div className={`rounded-2xl px-5 py-3.5 text-sm leading-relaxed font-medium transition-all ${
                  msg.role === "user"
                    ? "bg-blue-600 dark:bg-blue-700 text-white rounded-br-sm shadow-lg hover:shadow-xl"
                    : "bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 rounded-bl-sm border border-slate-200 dark:border-slate-600 shadow-sm hover:shadow-md"
                }`}>
                  {formatContent(msg.content)}
                </div>

                {/* Source tags + latency */}
                {msg.role === "assistant" && (msg.sources?.length || msg.latency) ? (
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    {msg.sources?.map(src => {
                      const { label, cls } = sourceLabel(src);
                      return (
                        <span key={src} className={`source-tag text-xs px-2.5 py-1 rounded-md font-semibold transition-all ${cls}`}>{label}</span>
                      );
                    })}
                    {msg.latency && (
                      <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">{msg.latency}ms</span>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          ))}

          {showProjects && (
            <div className="msg-assistant">
              <div className="w-full rounded-2xl rounded-bl-sm border border-slate-200 dark:border-slate-600 bg-gradient-to-br from-slate-50 to-slate-50 dark:from-slate-700 dark:to-slate-700/50 px-5 py-4 shadow-sm transition-colors duration-300">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <p className="text-base font-bold text-slate-900 dark:text-white">GitHub Projects</p>
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-600 px-3 py-1 rounded-full">{repos.length} repos</span>
                </div>

                {repos.length === 0 ? (
                  <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    No GitHub repos loaded yet. Run <span className="font-mono bg-slate-100 dark:bg-slate-600 px-2 py-1 rounded text-slate-800 dark:text-slate-200 font-semibold">python scripts/fetch_github.py</span>
                  </p>
                ) : (
                  <div className="space-y-3">
                    {repos.map((repo, index) => {
                      const isOpen = expandedRepo === repo.name;
                      return (
                        <div key={repo.name} className="rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 overflow-hidden hover:border-blue-300 dark:hover:border-blue-600 transition-all shadow-sm hover:shadow-md">
                          <button
                            onClick={() => toggleRepo(repo.name)}
                            className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-blue-50/30 dark:hover:bg-slate-700/50 transition-all"
                          >
                            <span className="flex items-center gap-3 min-w-0">
                              <span className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700 text-white text-xs font-bold flex items-center justify-center flex-shrink-0 shadow-md">
                                {index + 1}
                              </span>
                              <span className="text-sm font-bold text-slate-900 dark:text-white truncate">{repo.name}</span>
                              <span className="text-xs px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-semibold flex-shrink-0 border border-blue-100 dark:border-blue-800">
                                {repo.primary_language}
                              </span>
                            </span>
                            <span className="text-slate-400 dark:text-slate-500 text-lg font-light">{isOpen ? "−" : "+"}</span>
                          </button>

                          {isOpen && (
                            <div className="px-4 pb-4 pt-2 border-t border-slate-100 dark:border-slate-600 bg-gradient-to-b from-blue-50/20 dark:from-slate-700/50 to-transparent transition-colors duration-300">
                              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
                                {repo.description || repo.summary || "No README summary available yet."}
                              </p>

                              {repo.languages.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-3">
                                  {repo.languages.slice(0, 10).map(language => (
                                    <span
                                      key={language}
                                      className="text-xs px-2.5 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
                                    >
                                      {language}
                                    </span>
                                  ))}
                                </div>
                              )}

                              {repo.commits.length > 0 && (
                                <div className="mt-3">
                                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">Recent Commits</p>
                                  <ul className="space-y-1.5">
                                    {repo.commits.slice(0, 3).map(commit => (
                                      <li key={commit} className="text-xs text-slate-600 dark:text-slate-400 truncate font-medium bg-white/50 dark:bg-slate-700/50 px-2 py-1 rounded">
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
                                  className="inline-flex mt-3 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-bold bg-blue-50 dark:bg-blue-900/30 px-3 py-1.5 rounded-lg border border-blue-200 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-all"
                                >
                                  ↗ Open GitHub Repo
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
              <div className="bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-2xl rounded-bl-sm px-5 py-3.5 shadow-sm transition-colors duration-300">
                <div className="flex gap-2 items-center h-5">
                  <div className="typing-dot w-2.5 h-2.5 rounded-full bg-slate-400 dark:bg-slate-500 animate-pulse" />
                  <div className="typing-dot w-2.5 h-2.5 rounded-full bg-slate-400 dark:bg-slate-500 animate-pulse" style={{ animationDelay: "0.2s" }} />
                  <div className="typing-dot w-2.5 h-2.5 rounded-full bg-slate-400 dark:bg-slate-500 animate-pulse" style={{ animationDelay: "0.4s" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Booking widget */}
        {showBooking && (
          <div className="border-t border-blue-100 dark:border-blue-900 bg-gradient-to-b from-blue-50/60 dark:from-blue-900/20 to-white dark:to-slate-800 px-5 pt-4 pb-3 flex-shrink-0 shadow-lg transition-colors duration-300">
            <BookingWidget onClose={() => setShowBooking(false)} />
          </div>
        )}

        {/* Voice call widget */}
        {showVoiceCall && (
          <div className="border-t border-purple-100 dark:border-purple-900 bg-gradient-to-b from-purple-50/60 dark:from-purple-900/20 to-white dark:to-slate-800 px-5 pt-4 pb-3 flex-shrink-0 shadow-lg transition-colors duration-300">
            <VoiceCallWidget
              initialConfig={voiceConfig}
              onClose={() => setShowVoiceCall(false)}
            />
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-slate-100 dark:border-slate-700 p-4 flex gap-3 items-end flex-shrink-0 bg-gradient-to-t from-slate-50/50 dark:from-slate-700/50 to-white dark:to-slate-800 transition-colors duration-300">
          <input
            ref={inputRef}
            className="flex-1 border border-slate-200 dark:border-slate-600 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 dark:focus:ring-blue-400 focus:border-transparent placeholder:text-slate-400 dark:placeholder:text-slate-500 transition-all resize-none shadow-sm font-medium bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
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
            className="flex-shrink-0 w-11 h-11 bg-gradient-to-br from-blue-600 to-blue-700 dark:from-blue-700 dark:to-blue-800 hover:from-blue-700 hover:to-blue-800 dark:hover:from-blue-600 dark:hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl flex items-center justify-center transition-all shadow-lg hover:shadow-xl hover:scale-105"
            aria-label="Send message"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </main>
  );
}