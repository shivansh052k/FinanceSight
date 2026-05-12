import type { Message, Citation } from "../types";
import { CitationChip } from "./CitationChip";
import ReactMarkdown from "react-markdown";


interface Props {
  message: Message;
  onCitationClick: (citation: Citation) => void;
}

export function MessageBubble({ message, onCitationClick }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-white border border-gray-200 text-gray-900"
        }`}
      >
        <div className="text-sm [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_table]:w-full [&_table]:text-xs [&_th]:text-left [&_th]:font-semibold [&_td]:py-0.5">
        <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {message.disclaimer && (
          <p className="mt-2 text-xs text-amber-600 border-t border-amber-200 pt-2">
            {message.disclaimer}
          </p>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.map((c) => (
              <CitationChip
                key={c.id}
                citation={c}
                onClick={onCitationClick}
              />
            ))}
          </div>
        )}

        {message.citations && message.citations.length > 0 && (
        <div className="mt-2 space-y-1">
            <div className="flex flex-wrap gap-1">
            {message.citations.map((c) => (
                <CitationChip key={c.id} citation={c} onClick={onCitationClick} />
            ))}
            </div>
            <button
            onClick={() => onCitationClick(message.citations![0])}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
            📄 View →
            </button>
        </div>
        )}

        {message.insufficient_evidence && (
          <p className="mt-1 text-xs text-gray-400 italic">
            Insufficient evidence in ingested documents.
          </p>
        )}
      </div>
    </div>
  );
}