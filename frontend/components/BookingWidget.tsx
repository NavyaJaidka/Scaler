"use client";
import { useState } from "react";
import { backendPath } from "@/lib/backend";

interface Slot {
  start: string;
  display: string;
}

interface BookingWidgetProps {
  onClose: () => void;
}

export default function BookingWidget({ onClose }: BookingWidgetProps) {
  const [step, setStep] = useState<"form" | "slots" | "confirm" | "done">("form");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selected, setSelected] = useState<Slot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isValidEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

  const fetchSlots = async () => {
    if (!name.trim() || !isValidEmail(email)) {
      setError("Please enter your full name and a valid email address.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(backendPath("/slots"), { method: "POST" });
      const body = await res.text();
      const data = body ? JSON.parse(body) : {};
      if (!res.ok) throw new Error(data.detail || body || "Server error");
      if (!data.slots?.length) {
        setError("No available slots right now. Please try again later.");
        setLoading(false);
        return;
      }
      setSlots(data.slots);
      setStep("slots");
    } catch (err) {
      console.error("Slot request failed:", err);
      setError("Couldn't load available slots. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const confirmBooking = async () => {
    if (!selected) return;
    setStep("confirm");
    setLoading(true);
    setError("");
    try {
      const res = await fetch(backendPath("/book"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          slot_start: selected.start,
          notes: "Booked via AI persona chat UI",
        }),
      });
      const body = await res.text();
      const data = body ? JSON.parse(body) : {};
      if (data.success) {
        setStep("done");
      } else {
        setError(data.error || "Booking failed. Please try a different slot.");
        setStep("slots");
      }
    } catch (err) {
      console.error("Booking request failed:", err);
      setError("Something went wrong. Please try again.");
      setStep("slots");
    } finally {
      setLoading(false);
    }
  };

  // ── Done state ────────────────────────────────────────────────────────────
  if (step === "done") {
    return (
      <div className="booking-panel flex items-start gap-3 py-1">
        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
          <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-green-700">Meeting confirmed!</p>
          <p className="text-xs text-gray-500 mt-0.5">
            A calendar invite has been sent to <span className="font-medium">{email}</span>.
            {selected && ` See you ${selected.display}.`}
          </p>
        </div>
      </div>
    );
  }

  // ── Confirm loading state ─────────────────────────────────────────────────
  if (step === "confirm" && loading) {
    return (
      <div className="booking-panel flex items-center gap-3 py-2">
        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-gray-600">Confirming your booking...</span>
      </div>
    );
  }

  return (
    <div className="booking-panel space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-blue-100 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-blue-900">
            {step === "form" ? "Book an interview" : "Pick a time slot"}
          </p>
        </div>
        <button onClick={onClose}
          className="w-5 h-5 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Step: Form (name + email) */}
      {step === "form" && (
        <>
          <div className="flex gap-2">
            <div className="flex-1">
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent placeholder:text-gray-400"
                placeholder="Your full name"
                value={name}
                onChange={e => setName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && fetchSlots()}
              />
            </div>
            <div className="flex-1">
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent placeholder:text-gray-400"
                placeholder="your@email.com"
                value={email}
                type="email"
                onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === "Enter" && fetchSlots()}
              />
            </div>
          </div>
          {error && <p className="text-xs text-red-500 flex items-center gap-1">
            <span>⚠</span> {error}
          </p>}
          <button
            onClick={fetchSlots}
            disabled={loading || !name.trim() || !email.trim()}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors"
          >
            {loading ? (
              <>
                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Loading slots...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                See available times
              </>
            )}
          </button>
        </>
      )}

      {/* Step: Slot selection */}
      {step === "slots" && (
        <>
          <div className="flex flex-wrap gap-1.5">
            {slots.map(slot => (
              <button
                key={slot.start}
                onClick={() => setSelected(slot)}
                className={`text-xs px-3 py-2 rounded-lg border transition-all duration-150 ${
                  selected?.start === slot.start
                    ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                    : "bg-white text-gray-700 border-gray-200 hover:border-blue-400 hover:text-blue-700"
                }`}
              >
                {slot.display}
              </button>
            ))}
          </div>
          {error && <p className="text-xs text-red-500">⚠ {error}</p>}
          <div className="flex gap-2 items-center">
            <button
              onClick={() => { setStep("form"); setSelected(null); setError(""); }}
              className="text-xs text-gray-500 hover:text-gray-700 underline"
            >
              ← Change details
            </button>
            {selected && (
              <button
                onClick={confirmBooking}
                disabled={loading}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors ml-auto"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                Confirm {selected.display}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}