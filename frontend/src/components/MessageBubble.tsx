import ReactMarkdown from "react-markdown";
import type { Message, Citation } from "../types";
import { CitationChip } from "./CitationChip";

interface Props {
  message: Message;
  onCitationClick: (citation: Citation) => void;
}

export function MessageBubble({ message, onCitationClick }: Props) {
  const isUser = message.role === "user";

  return (
    <div className="mb-8 px-6">
      <div className="flex items-center gap-2 mb-2">
        {isUser ? (
          <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">You</span>
        ) : (
          <>
            <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
              <span className="text-white text-[9px] font-bold">FS</span>
            </div>
            <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">FinanceSight</span>
          </>
        )}
      </div>

      <div className={isUser ? "pl-0" : "pl-7"}>
        {isUser ? (
          <p className="text-sm text-zinc-900 dark:text-zinc-100">{message.content}</p>
        ) : (
          <>
            <div className="text-sm text-zinc-900 dark:text-zinc-100 leading-relaxed [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mt-1 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:mt-0.5 [&_table]:w-full [&_table]:text-xs [&_table]:border-collapse [&_th]:text-left [&_th]:font-semibold [&_th]:border-b [&_th]:border-zinc-200 dark:[&_th]:border-zinc-700 [&_th]:pb-1 [&_td]:py-1 [&_td]:border-b [&_td]:border-zinc-100 dark:[&_td]:border-zinc-800 [&_p]:mb-2 last:[&_p]:mb-0">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>

            {message.disclaimer && (
              <p className="mt-3 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2">
                {message.disclaimer}
              </p>
            )}

            {message.citations && message.citations.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <div className="flex flex-wrap gap-1.5">
                  {message.citations.map((c) => (
                    <CitationChip key={c.id} citation={c} onClick={onCitationClick} />
                  ))}
                </div>
                                <button
                  onClick={() => onCitationClick(message.citations![0])}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium"
                >
                  📄 View source →
                </button>
              </div>
            )}

            {message.insufficient_evidence && (
              <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-600 italic">
                Insufficient evidence in ingested documents.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}