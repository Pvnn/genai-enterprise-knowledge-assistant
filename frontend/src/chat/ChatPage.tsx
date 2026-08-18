/**
 * Main ChatPage component.
 * Owner: P7
 *
 * Implements:
 *   - Chat UI orchestration with streaming SSE responses from POST /chat
 *   - Document Library explorer view
 *   - Grounded citations display (Section 5)
 *   - Refusal (low confidence) and Conflict (version dispute) handling
 *   - Clarifying question interaction (Stage 1 / Priority 2)
 *   - Thumbs up/down feedback capture (Priority 2)
 *   - Dark and light theme synchronization
 * Styled with Claude-inspired Civic Indigo, Warm Paper, Deep Slate, and Seal Gold palette.
 */

import React, { useState, useEffect, useRef } from "react";
import {
  PaperPlaneRight,
  Stop,
  List,
  ShieldCheck,
  Sparkle,
  ArrowClockwise,
  Files,
  ChatCircleText,
  Briefcase,
  GraduationCap,
  CurrencyCircleDollar,
  Scales,
} from "@phosphor-icons/react";
import { ChatMessage, Conversation } from "./types";
import { streamChat } from "../api/client";
import ChatSidebar from "./ChatSidebar";
import ChatMessageItem from "./ChatMessageItem";
import DocumentsLibrary from "./DocumentsLibrary";

const DEFAULT_TENANT_ID =
  localStorage.getItem("tenant_id") || "00000000-0000-0000-0000-000000000001";

const STORAGE_KEY_CONVERSATIONS = "genai_assistant_conversations";
const STORAGE_KEY_THEME = "genai_assistant_theme";

export const ChatPage: React.FC = () => {
  // Theme state
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_THEME);
    if (saved !== null) return saved === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  // Current view state: chat or documents library
  const [currentView, setCurrentView] = useState<"chat" | "documents">("chat");

  // Sidebar mobile toggle
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Tenant state
  const [tenantId, setTenantId] = useState<string>(DEFAULT_TENANT_ID);

  // Conversations state
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_CONVERSATIONS);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // Fall through to initial state
    }
    const initialId = crypto.randomUUID();
    return [
      {
        id: initialId,
        title: "New Policy Inquiry",
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    ];
  });

  const [activeConvId, setActiveConvId] = useState<string>(() => {
    return conversations[0]?.id || crypto.randomUUID();
  });

  const [inputQuery, setInputQuery] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Synchronize dark mode class to html element and localStorage
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
      localStorage.setItem(STORAGE_KEY_THEME, "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem(STORAGE_KEY_THEME, "light");
    }
  }, [darkMode]);

  // Persist conversations to localStorage
  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY_CONVERSATIONS,
      JSON.stringify(conversations)
    );
  }, [conversations]);

  // Auto-scroll to latest message
  useEffect(() => {
    if (currentView === "chat") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [conversations, isStreaming, currentView]);

  // Auto-resize input textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [inputQuery]);

  const currentConversation =
    conversations.find((c) => c.id === activeConvId) || conversations[0];

  const handleNewConversation = () => {
    const newId = crypto.randomUUID();
    const newConv: Conversation = {
      id: newId,
      title: "New Policy Inquiry",
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveConvId(newId);
    setInputQuery("");
    setCurrentView("chat");
  };

  const handleDeleteConversation = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id);
      if (filtered.length === 0) {
        const freshId = crypto.randomUUID();
        return [
          {
            id: freshId,
            title: "New Policy Inquiry",
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          },
        ];
      }
      return filtered;
    });
    if (activeConvId === id) {
      const remaining = conversations.filter((c) => c.id !== id);
      if (remaining.length > 0) {
        setActiveConvId(remaining[0].id);
      }
    }
  };

  const handleSendMessage = async (queryText?: string) => {
    const query = (queryText ?? inputQuery).trim();
    if (!query || isStreaming) return;

    setCurrentView("chat");
    setInputQuery("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const userMessageId = crypto.randomUUID();
    const assistantMessageId = crypto.randomUUID();
    const nowIso = new Date().toISOString();

    const userMsg: ChatMessage = {
      id: userMessageId,
      role: "user",
      content: query,
      status: "done",
      timestamp: nowIso,
    };

    const assistantMsg: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      status: "streaming",
      timestamp: nowIso,
    };

    // Update conversation with initial messages
    setConversations((prev) =>
      prev.map((conv) => {
        if (conv.id === activeConvId) {
          const isFirstMessage = conv.messages.length === 0;
          return {
            ...conv,
            title: isFirstMessage ? query.slice(0, 36) : conv.title,
            messages: [...conv.messages, userMsg, assistantMsg],
            updatedAt: nowIso,
          };
        }
        return conv;
      })
    );

    setIsStreaming(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulatedContent = "";

    await streamChat(
      {
        query,
        tenant_id: tenantId,
        conversation_id: activeConvId,
      },
      {
        onToken: (tokenEvent) => {
          accumulatedContent += tokenEvent.content;
          setConversations((prev) =>
            prev.map((conv) => {
              if (conv.id === activeConvId) {
                return {
                  ...conv,
                  messages: conv.messages.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          content: accumulatedContent,
                          status: "streaming",
                        }
                      : m
                  ),
                };
              }
              return conv;
            })
          );
        },
        onClarify: (clarifyEvent) => {
          setConversations((prev) =>
            prev.map((conv) => {
              if (conv.id === activeConvId) {
                return {
                  ...conv,
                  messages: conv.messages.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          clarify: clarifyEvent,
                          status: "done",
                        }
                      : m
                  ),
                };
              }
              return conv;
            })
          );
          setIsStreaming(false);
        },
        onFinal: (finalEvent) => {
          setConversations((prev) =>
            prev.map((conv) => {
              if (conv.id === activeConvId) {
                return {
                  ...conv,
                  messages: conv.messages.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          content: finalEvent.answer || accumulatedContent,
                          final: finalEvent,
                          status: "done",
                        }
                      : m
                  ),
                };
              }
              return conv;
            })
          );
          setIsStreaming(false);
        },
        onError: (err) => {
          const detail =
            "detail" in err
              ? err.detail
              : err instanceof Error
              ? err.message
              : "Failed to stream answer from backend.";

          setConversations((prev) =>
            prev.map((conv) => {
              if (conv.id === activeConvId) {
                return {
                  ...conv,
                  messages: conv.messages.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          status: "error",
                          errorDetail: detail,
                        }
                      : m
                  ),
                };
              }
              return conv;
            })
          );
          setIsStreaming(false);
        },
      },
      controller.signal
    );

    setIsStreaming(false);
    abortControllerRef.current = null;
  };

  const handleAbort = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);

      setConversations((prev) =>
        prev.map((conv) => {
          if (conv.id === activeConvId) {
            return {
              ...conv,
              messages: conv.messages.map((m) =>
                m.status === "streaming" ? { ...m, status: "done" } : m
              ),
            };
          }
          return conv;
        })
      );
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFeedbackUpdate = (messageId: string, vote: "up" | "down") => {
    setConversations((prev) =>
      prev.map((conv) => {
        if (conv.id === activeConvId) {
          return {
            ...conv,
            messages: conv.messages.map((m) =>
              m.id === messageId ? { ...m, feedbackSubmitted: vote } : m
            ),
          };
        }
        return conv;
      })
    );
  };

  const handleAskAboutDoc = (docTitle: string) => {
    setCurrentView("chat");
    handleSendMessage(`What are the key policy requirements and provisions outlined in ${docTitle}?`);
  };

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-canvas text-ink font-sans">
      {/* Left Sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelectConversation={setActiveConvId}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        currentView={currentView}
        onSelectView={setCurrentView}
        tenantId={tenantId}
        onTenantChange={setTenantId}
        darkMode={darkMode}
        onToggleDarkMode={() => setDarkMode(!darkMode)}
        isOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      {/* Central Viewport */}
      <main className="flex-1 flex flex-col h-full min-w-0 bg-canvas border-l border-hairline">
        {/* Top Navbar */}
        <header className="h-14 px-4 sm:px-6 border-b border-hairline flex items-center justify-between bg-surface/80 backdrop-blur-xs shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="p-1.5 rounded-lg text-ink-muted hover:text-ink md:hidden"
            >
              <List size={20} />
            </button>
            <div className="flex items-center gap-2.5">
              <ShieldCheck size={18} className="text-primary-brand" />
              <h1 className="text-sm font-semibold text-ink truncate">
                {currentView === "documents"
                  ? "Institutional Knowledge Base"
                  : currentConversation?.title || "Knowledge Assistant"}
              </h1>
            </div>
          </div>

          {/* View Tab Buttons & Status Indicator */}
          <div className="flex items-center gap-2 text-xs">
            <div className="hidden sm:flex items-center p-1 rounded-xl bg-surface-muted border border-hairline">
              <button
                type="button"
                onClick={() => setCurrentView("chat")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all font-medium ${
                  currentView === "chat"
                    ? "bg-surface text-ink shadow-2xs border border-hairline"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                <ChatCircleText size={14} />
                <span>Chat</span>
              </button>
              <button
                type="button"
                onClick={() => setCurrentView("documents")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all font-medium ${
                  currentView === "documents"
                    ? "bg-surface text-ink shadow-2xs border border-hairline"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                <Files size={14} />
                <span>Documents</span>
              </button>
            </div>

            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface border border-hairline text-ink-muted font-medium text-[11px]">
              <span className="w-2 h-2 rounded-full bg-accent-gold animate-pulse" />
              <span>Grounded Assistant</span>
            </div>
          </div>
        </header>

        {/* View Switch */}
        {currentView === "documents" ? (
          <DocumentsLibrary
            tenantId={tenantId}
            onAskAboutDocument={handleAskAboutDoc}
          />
        ) : (
          <>
            {/* Messages Scroll Area */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 py-6">
              <div className="max-w-3xl mx-auto space-y-5">
                {/* Empty State with Rich Categorized Starters */}
                {currentConversation?.messages.length === 0 && (
                  <div className="py-8 sm:py-12 text-center space-y-6 animate-in fade-in duration-200">
                    <div className="w-12 h-12 mx-auto rounded-2xl bg-surface border border-hairline flex items-center justify-center text-accent-gold shadow-xs">
                      <Sparkle size={24} weight="bold" />
                    </div>
                    <div className="space-y-1.5 max-w-lg mx-auto">
                      <h3 className="text-lg sm:text-xl font-bold text-ink tracking-tight">
                        Institutional Knowledge Assistant
                      </h3>
                      <p className="text-xs sm:text-sm text-ink-muted leading-relaxed">
                        Search verified circulars, leave rules, academic ordinances, and procurement procedures with strict citation tracing.
                      </p>
                    </div>

                    {/* Categorized Starter Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-left max-w-2xl mx-auto pt-2">
                      {[
                        {
                          icon: Briefcase,
                          domain: "Human Resources",
                          label: "Maternity Leave Entitlement",
                          query: "What is the maternity leave entitlement for teaching faculty?",
                        },
                        {
                          icon: CurrencyCircleDollar,
                          domain: "Finance & Accounts",
                          label: "Official Travel & Per Diem",
                          query: "What are the allowed daily allowance rates for official travel?",
                        },
                        {
                          icon: GraduationCap,
                          domain: "Academic Affairs",
                          label: "Attendance & Grading Rules",
                          query: "What is the minimum attendance requirement for semester examinations?",
                        },
                        {
                          icon: Scales,
                          domain: "Administration",
                          label: "Procurement Thresholds",
                          query: "What are the financial threshold limits for departmental purchase committees?",
                        },
                      ].map((card, i) => {
                        const Icon = card.icon;
                        return (
                          <button
                            key={i}
                            type="button"
                            onClick={() => handleSendMessage(card.query)}
                            className="p-4 rounded-2xl border border-hairline bg-surface hover:border-accent-gold/60 text-left transition-all group shadow-2xs flex flex-col justify-between space-y-2 hover:-translate-y-0.5 active:scale-[0.98]"
                          >
                            <div className="flex items-center justify-between">
                              <span className="flex items-center gap-1.5 text-[11px] font-semibold text-accent-gold">
                                <Icon size={14} weight="bold" />
                                <span>{card.domain}</span>
                              </span>
                              <span className="text-[11px] text-ink-muted font-medium group-hover:text-primary-brand transition-colors">
                                Ask &rarr;
                              </span>
                            </div>
                            <span className="text-xs font-medium text-ink leading-snug">
                              {card.query}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Render Messages */}
                {currentConversation?.messages.map((message) => (
                  <ChatMessageItem
                    key={message.id}
                    message={message}
                    onClarifyRespond={(reply) => handleSendMessage(reply)}
                    onFeedbackUpdate={handleFeedbackUpdate}
                  />
                ))}

                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Bottom Input Sticky Bar */}
            <div className="p-4 border-t border-hairline bg-canvas/90 backdrop-blur-xs shrink-0">
              <div className="max-w-3xl mx-auto">
                <div className="relative flex items-end gap-2 rounded-2xl border border-hairline bg-surface p-2.5 focus-within:border-primary-brand shadow-xs transition-all">
                  <textarea
                    ref={textareaRef}
                    value={inputQuery}
                    onChange={(e) => setInputQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about any circular, policy, or institutional regulation..."
                    rows={1}
                    disabled={isStreaming}
                    className="w-full resize-none bg-transparent px-2 py-1 text-sm text-ink placeholder-ink-muted focus:outline-none max-h-44"
                  />

                  {isStreaming ? (
                    <button
                      type="button"
                      onClick={handleAbort}
                      className="p-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white transition-colors flex items-center justify-center shrink-0"
                      title="Stop generating"
                    >
                      <Stop size={18} weight="fill" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleSendMessage()}
                      disabled={!inputQuery.trim()}
                      className="p-2 rounded-xl bg-primary-brand hover:opacity-90 text-white disabled:opacity-40 transition-all flex items-center justify-center shrink-0 active:scale-95 shadow-2xs"
                      title="Send query (Enter)"
                    >
                      <PaperPlaneRight size={18} weight="bold" />
                    </button>
                  )}
                </div>

                <div className="mt-2 flex items-center justify-between text-[11px] text-ink-muted px-1">
                  <span>Press Enter to send, Shift+Enter for new line</span>
                  <span className="flex items-center gap-1">
                    <ArrowClockwise size={11} className="text-accent-gold" />
                    <span>Strict Grounded Retrieval</span>
                  </span>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
};

export default ChatPage;
