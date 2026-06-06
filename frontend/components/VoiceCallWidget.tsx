"use client";
import { useEffect, useState } from "react";
import { backendPath } from "@/lib/backend";

interface VoiceConfig {
  enabled: boolean;
  provider?: string;
  stream_url?: string;
  configured?: Record<string, boolean>;
}

interface VoiceCallWidgetProps {
  initialConfig?: VoiceConfig | null;
  onClose: () => void;
}

export default function VoiceCallWidget({ initialConfig, onClose }: VoiceCallWidgetProps) {
  const [config, setConfig] = useState<VoiceConfig | null>(initialConfig ?? null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState(
    "Hi there! I'm the AI representative for Navya Jaidka. I can answer questions about their background, projects, and interview availability."
  );
  const [loadingConfig, setLoadingConfig] = useState(!initialConfig);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
      setLoadingConfig(false);
      return;
    }

    let cancelled = false;
    setLoadingConfig(true);
    setError("");

    fetch(backendPath("/voice/config"))
      .then(r => r.json())
      .then(data => {
        if (!cancelled) setConfig(data);
      })
      .catch(() => {
        if (!cancelled) setError("Voice configuration could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoadingConfig(false);
      });

    return () => {
      cancelled = true;
    };
  }, [initialConfig]);

  const requiredConfigReady = config ? Boolean(
    config?.configured?.vobiz_auth_id &&
    config?.configured?.vobiz_auth_token &&
    config?.configured?.vobiz_caller_id &&
    config?.configured?.vobiz_answer_url &&
    config?.configured?.vobiz_respond_url
  ) : true;

  const startCall = async () => {
    if (!phone.trim()) {
      setError("Please enter your phone number with country code, for example +919876543210.");
      return;
    }

    setSubmitting(true);
    setStatus("");
    setError("");

    try {
      const res = await fetch(backendPath("/voice/call"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          phone: phone.trim(),
          message: message.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      }
      setStatus(data.message || "Call started. You should receive a phone call shortly.");
      setPhone("");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Unable to start the voice call.";
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-indigo-900 dark:text-indigo-300">Request a voice call</p>
          <p className="text-xs text-indigo-700 dark:text-indigo-400 mt-0.5">
            Enter your number and Vobiz will call you with the AI representative.
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-400 text-xs px-2 py-1"
          aria-label="Close voice call widget"
        >
          x
        </button>
      </div>

      {!loadingConfig && !requiredConfigReady ? (
        <div className="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/20 px-3 py-3">
          <p className="text-sm font-semibold text-amber-900 dark:text-amber-300">Voice calling is not fully configured</p>
          <p className="mt-1 text-xs text-amber-800 dark:text-amber-400">
            Set <span className="font-mono">VOBIZ_AUTH_ID</span>,
            <span className="font-mono"> VOBIZ_AUTH_TOKEN</span>,
            <span className="font-mono"> VOBIZ_CALLER_ID</span>, and
            <span className="font-mono"> PUBLIC_BACKEND_URL</span>.
          </p>
        </div>
      ) : null}

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">Your name</label>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Recruiter name"
          className="w-full rounded-lg border border-gray-200 dark:border-slate-600 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-400 placeholder:text-gray-400 dark:placeholder:text-slate-500 bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
          disabled={submitting}
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">Phone number</label>
        <input
          value={phone}
          onChange={e => setPhone(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && !submitting) startCall();
          }}
          placeholder="+919876543210"
          className="w-full rounded-lg border border-gray-200 dark:border-slate-600 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-400 placeholder:text-gray-400 dark:placeholder:text-slate-500 bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
          disabled={submitting}
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">First message</label>
        <textarea
          value={message}
          onChange={e => setMessage(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-gray-200 dark:border-slate-600 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-400 placeholder:text-gray-400 dark:placeholder:text-slate-500 bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
          disabled={submitting}
        />
      </div>

      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      {status && <p className="text-xs text-emerald-700 dark:text-emerald-400">{status}</p>}

      <button
        type="button"
        onClick={startCall}
        disabled={submitting || !phone.trim()}
        className="w-full rounded-xl bg-indigo-600 dark:bg-indigo-700 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 dark:hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
      >
        {submitting ? "Starting call..." : "Start voice call"}
      </button>

    </div>
  );
}