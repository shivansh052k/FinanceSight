import { useRef, useEffect, useState, KeyboardEvent } from "react";
import type { Message, Citation } from "../types";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: Message[];
  loading: boolean;
  error: string | null;
  onSend: (query: string) => void;
  onCitationClick: (citation: Citation) => void;
}

export function ChatPane({ messages, loading, error, onSend, onCitationClick }: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setInput("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto py-8">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-8">
            <div className="w-12 h-12 rounded-full bg-blue-600 flex items-center justify-center mb-4">
              <span className="text-white text-lg font-bold">FS</span>
            </div>
            <h2 className="text-lg font-semibold text-zinc-800 mb-1">FinanceSight</h2>
            <p className="text-sm text-zinc-500 max-w-sm">
              Upload SEC 10-K filings from the sidebar, then ask questions about revenues, risks, and financials.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} onCitationClick={onCitationClick} />
        ))}

        {loading && (
        <div className="mb-8 px-6">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
              <span className="text-white text-[9px] font-bold">FS</span>
            </div>
            <span className="text-xs font-semibold text-zinc-500">FinanceSight</span>
          </div>
          <div className="pl-7 flex items-center gap-1.5 text-sm text-zinc-400">
            <span>Thinking</span>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1 h-1 bg-zinc-300 rounded-full animate-bounce"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        </div>
      )}

        {error && (
          <p className="text-red-500 text-sm text-center px-4 mb-4">{error}</p>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-zinc-200 px-4 py-4">
        <div className="flex gap-3 items-end max-w-3xl mx-auto">
          <textarea
            className="flex-1 resize-none rounded-xl border border-zinc-300 px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-zinc-50 transition-shadow"
            rows={2}
            placeholder="Ask about revenues, risks, comparisons..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="px-4 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            Send
          </button>
        </div>
        <p className="text-[11px] text-zinc-400 text-center mt-2">Enter to send · Shift+Enter for newline</p>
      </div>
    </div>
  );
}