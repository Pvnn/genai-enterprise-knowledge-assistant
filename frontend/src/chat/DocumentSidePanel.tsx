import React, { useState, useEffect, useRef } from "react";
import { X, SpinnerGap, FileText,  } from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import { getDocumentContent } from "../api/client";

interface DocumentSidePanelProps {
  documentId: string;
  citationText: string | null;
  onClose: () => void;
}

export const DocumentSidePanel: React.FC<DocumentSidePanelProps> = ({
  documentId,
  citationText,
  onClose,
}) => {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    getDocumentContent(documentId)
      .then((text) => {
        if (isMounted) {
          setContent(text);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "Failed to load document");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [documentId]);

  // Attempt to scroll to citation text once loaded
  useEffect(() => {
    if (!loading && citationText && contentRef.current) {
      const timer = setTimeout(() => {
        if (!contentRef.current) return;
        
        // 1. Normalize a string by removing all non-alphanumeric characters and lowercasing
        const normalize = (s: string) => s.replace(/[^a-z0-9]/gi, "").toLowerCase();
        
        const normCitation = normalize(citationText);
        if (normCitation.length < 10) return; // Too short to reliably match

        // 2. Get all block-level elements that usually contain text
        const elements = Array.from(
          contentRef.current.querySelectorAll("p, h1, h2, h3, h4, h5, h6, li, td, th, blockquote")
        ) as HTMLElement[];

        let bestMatchElement: HTMLElement | null = null;
        let maxMatchLength = 0;

        for (const el of elements) {
          const normElText = normalize(el.textContent || "");
          if (normElText.length < 5) continue;

          // Try prefix lengths from Math.min(150, normCitation.length) down to 15
          for (let prefixLen = Math.min(150, normCitation.length); prefixLen >= 15; prefixLen -= 5) {
            const prefix = normCitation.substring(0, prefixLen);
            if (normElText.includes(prefix)) {
              if (prefixLen > maxMatchLength) {
                maxMatchLength = prefixLen;
                bestMatchElement = el;
              }
              break; 
            }
          }
        }

        // Fallback: If prefix matching fails completely, find the element that 
        // is most fully contained within the citation text.
        if (!bestMatchElement) {
           for (const el of elements) {
             const normElText = normalize(el.textContent || "");
             if (normElText.length < 15) continue;
             if (normCitation.includes(normElText)) {
                if (normElText.length > maxMatchLength) {
                   maxMatchLength = normElText.length;
                   bestMatchElement = el;
                }
             }
           }
        }

        if (bestMatchElement) {
          // Highlight the element
          const originalBg = bestMatchElement.style.backgroundColor;
          const originalTransition = bestMatchElement.style.transition;
          const originalRadius = bestMatchElement.style.borderRadius;

          bestMatchElement.style.backgroundColor = 'rgba(234, 179, 8, 0.4)'; // accent-gold with opacity
          bestMatchElement.style.borderRadius = '4px';
          bestMatchElement.style.transition = 'background-color 2s ease';
          
          bestMatchElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
          
          // Fade out highlight after a few seconds
          setTimeout(() => {
             bestMatchElement!.style.backgroundColor = 'transparent';
             setTimeout(() => {
                 bestMatchElement!.style.transition = originalTransition;
                 bestMatchElement!.style.backgroundColor = originalBg;
                 bestMatchElement!.style.borderRadius = originalRadius;
             }, 2000);
          }, 3000);
        }
      }, 500); // 500ms allows images and markdown to fully layout

      return () => clearTimeout(timer);
    }
  }, [loading, citationText, content]);

  return (
    <div className="h-full flex flex-col bg-surface border-l border-hairline shadow-lg animate-in slide-in-from-right-4 duration-200">
      <div className="flex items-center justify-between p-4 border-b border-hairline bg-surface z-10 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-primary-brand/10 border border-primary-brand/20 flex items-center justify-center text-primary-brand shrink-0">
            <FileText size={16} weight="bold" />
          </div>
          <div className="truncate min-w-0 pr-2">
            <h3 className="text-sm font-bold text-ink truncate">Document Viewer</h3>
            <p className="text-[10px] text-ink-muted truncate">ID: {documentId}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-xl text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 relative" ref={contentRef}>
        {loading ? (
          <div className="flex flex-col items-center justify-center h-full text-ink-muted space-y-3">
            <SpinnerGap size={24} className="animate-spin text-primary-brand" />
            <p className="text-xs">Fetching source document...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full text-rose-500 space-y-2">
            <p className="text-sm font-medium">Error loading document</p>
            <p className="text-xs opacity-80">{error}</p>
          </div>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none text-ink">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentSidePanel;
