"use client";
import { useState, useEffect } from "react";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export default function VoiceCallWidget({ onClose }: { onClose: () => void }) {
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("Hi, I'm calling on behalf of [YOUR NAME] to discuss their background and interview availability.");
  const [status, setStatus] = useState("");
  const [healthStatus, setHealthStatus] = useState("");
  const [isWebhookHealthy, setIsWebhookHealthy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [healthLoading, setHealthLoading] = useState(false);
  const [error, setError] = useState("");

  const postJson = async (url: string, body: object) => {
    if (typeof fetch === "function") {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || `HTTP ${res.status}`);
      }
      return data;
    }

    return await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText || "{}");
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(data);
          } else {
            reject(new Error(data?.error || `HTTP ${xhr.status}`));
          }
        } catch (error) {
          reject(error);
        }
      };
      xhr.onerror = () => reject(new Error("Network error while sending the request."));
      xhr.send(JSON.stringify(body));
    });
  };

  const getJson = async (url: string) => {
    if (typeof fetch === "function") {
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || `HTTP ${res.status}`);
      }
      return data;
    }

    return await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("GET", url);
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText || "{}");
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(data);
          } else {
            reject(new Error(data?.error || `HTTP ${xhr.status}`));
          }
        } catch (error) {
          reject(error);
        }
      };
      xhr.onerror = () => reject(new Error("Network error while checking health."));
      xhr.send();
    });
  };

  const checkHealth = async () => {
    setHealthLoading(true);
    setError("");
    setStatus("");
    setHealthStatus("");
    try {
      const data = await getJson(`${backendUrl}/webhook/vapi/health`);
      setHealthStatus(data.message || "Webhook health check passed.");
      setIsWebhookHealthy(true);
      return true;
    } catch (err: any) {
      console.error("Health check error:", err);
      setHealthStatus("");
      setIsWebhookHealthy(false);
      setError(err?.message || "Health check failed. Make sure the webhook service is running.");
      return false;
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const startCall = async () => {
    if (!isWebhookHealthy) {
      const healthy = await checkHealth();
      if (!healthy) {
        setError("Webhook is not healthy. Please fix the webhook before starting a call.");
        return;
      }
    }
    if (!phone.trim()) {
      setError("Please enter your phone number.");
      return;
    }
    setLoading(true);
    setError("");
    setStatus("");
    try {
      const data = await postJson(`${backendUrl}/voice/call`, {
        phone: phone.trim(),
        message: message.trim()
      });
      setStatus(data.message || "Call started. You should receive a phone call shortly.");
      setPhone("");
    } catch (err: any) {
      console.error("Voice call error:", err);
      setError(err?.message || "Unable to reach the voice service. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-blue-800">📞 Request a voice call</p>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
      </div>
      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-700">Phone number</label>
        <input
          value={phone}
          onChange={e => setPhone(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && !loading && phone.trim()) {
              startCall();
            }
          }}
          placeholder="+1234567890"
          className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          disabled={loading}
        />
      </div>
      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-700">Call message</label>
        <textarea
          value={message}
          onChange={e => setMessage(e.target.value)}
          rows={3}
          className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          disabled={loading}
        />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {healthStatus && <p className="text-xs text-emerald-700">{healthStatus}</p>}
      {status && <p className="text-xs text-green-700">{status}</p>}
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={checkHealth}
          disabled={healthLoading}
          className="w-full bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-800 px-4 py-2 rounded-xl text-sm font-medium border border-slate-200"
        >
          {healthLoading ? "Checking webhook health..." : "Check webhook health"}
        </button>
        <button
          type="button"
          onClick={startCall}
          disabled={loading || !phone.trim() || !isWebhookHealthy}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-xl text-sm font-medium"
        >
          {loading ? "Starting call..." : "Start voice call"}
        </button>
      </div>
    </div>
  );
}
