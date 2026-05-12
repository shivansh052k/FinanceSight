import { useState, useCallback } from "react";
import { queryDocuments } from "../api/client";
import type { Message, Citation } from "../types";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim()) return;

    const userMessage: Message = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);

    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const response = await queryDocuments({
        query,
        conversation_history: history,
      });

      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        intent: response.intent,
        confidence: response.confidence,
        disclaimer: response.disclaimer,
        insufficient_evidence: response.insufficient_evidence,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError("Failed to get a response. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [messages]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, loading, error, sendMessage, clearMessages };
}