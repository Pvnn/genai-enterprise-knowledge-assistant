/**
 * ChatSidebar Component.
 * Owner: P7
 *
 * Provides conversation thread history, view switching, tenant scope, theme toggling, and logout UI hook.
 * Branded for NODI with Grounded enterprise knowledge.
 */

import React, { useEffect, useState } from "react";
import { getMe } from "../api/client";
import {
  Plus,
  ChatCircleText,
  Trash,
  Sun,
  Moon,
  Files,
  X,
  SignOut,
  ShieldCheck,
} from "@phosphor-icons/react";
import { Conversation } from "./types";
import NodiLogo from "./NodiLogo";

interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string, e: React.MouseEvent) => void;
  currentView: "chat" | "documents";
  onSelectView: (view: "chat" | "documents") => void;
  
  onTenantChange: (newTenant: string) => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
  isOpen: boolean;
  onCloseMobile: () => void;
  onLogout?: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  conversations,
  activeId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  currentView,
  onSelectView,
  
  darkMode,
  onToggleDarkMode,
  isOpen,
  onCloseMobile,
  onLogout,
}) => {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    getMe().then(user => {
      if (user && user.email) {
        setEmail(user.email);
      }
    }).catch(err => console.error("Failed to fetch user email", err));
  }, []);

  const username = email ? email.split("@")[0] : "User";
  const organization = email ? email.split("@")[1].split(".")[0] : "Organization";

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs md:hidden"
        />
      )}

      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-72 flex flex-col justify-between border-r border-hairline bg-surface-muted text-ink transition-transform duration-200 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* Header with NODI Logo */}
        <div className="p-4 border-b border-hairline space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-surface border border-hairline flex items-center justify-center text-primary-brand shadow-2xs shrink-0">
                <NodiLogo size={22} className="text-primary-brand" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-ink tracking-tight">
                  NODI
                </h2>
                <p className="text-[11px] text-ink-muted">
                  Grounded enterprise knowledge
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onCloseMobile}
              className="p-1 rounded-lg text-ink-muted hover:text-ink md:hidden"
            >
              <X size={18} />
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              onSelectView("chat");
              onNewConversation();
              onCloseMobile();
            }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-medium rounded-xl bg-surface hover:bg-surface-elevated border border-hairline text-ink shadow-2xs transition-all active:scale-[0.98]"
          >
            <Plus size={14} weight="bold" className="text-accent-gold" />
            <span>New Chat</span>
          </button>
        </div>

        {/* View Switcher & Conversation History */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* Main Navigation Tabs */}
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => {
                onSelectView("chat");
                onCloseMobile();
              }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors ${
                currentView === "chat"
                  ? "bg-surface text-ink font-semibold border border-hairline shadow-2xs"
                  : "text-ink-muted hover:text-ink hover:bg-surface"
              }`}
            >
              <ChatCircleText
                size={16}
                className={currentView === "chat" ? "text-primary-brand" : "text-ink-muted"}
              />
              <span>Chat Workspace</span>
            </button>

            <button
              type="button"
              onClick={() => {
                onSelectView("documents");
                onCloseMobile();
              }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors ${
                currentView === "documents"
                  ? "bg-surface text-ink font-semibold border border-hairline shadow-2xs"
                  : "text-ink-muted hover:text-ink hover:bg-surface"
              }`}
            >
              <Files
                size={16}
                className={currentView === "documents" ? "text-accent-gold" : "text-ink-muted"}
              />
              <span>Document Library</span>
            </button>

            {(localStorage.getItem("user_role") || "member") === "admin" && (
              <button
                type="button"
                onClick={() => {
                  window.history.pushState({}, "", "/admin");
                  window.dispatchEvent(new PopStateEvent("popstate"));
                  onCloseMobile();
                }}
                className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs text-ink-muted hover:text-ink hover:bg-surface/50 transition-colors"
              >
                <span className="flex items-center gap-2.5">
                  <ShieldCheck size={16} className="text-accent-gold" weight="bold" />
                  <span>Admin Dashboard</span>
                </span>
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-accent-gold/10 text-accent-gold">
                  Admin
                </span>
              </button>
            )}
          </div>

          {/* Active / Past Conversation Threads */}
          <div>
            <div className="px-2 pb-1.5 pt-2 text-[11px] font-semibold text-ink-muted uppercase tracking-wider">
              Recent Threads
            </div>
            {conversations.length === 0 ? (
              <div className="px-2 py-4 text-xs text-ink-muted text-center">
                No active conversations yet.
              </div>
            ) : (
              <div className="space-y-1">
                {conversations.map((conv) => {
                  const isActive = conv.id === activeId && currentView === "chat";
                  return (
                    <div
                      key={conv.id}
                      onClick={() => {
                        onSelectView("chat");
                        onSelectConversation(conv.id);
                        onCloseMobile();
                      }}
                      className={`group flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-colors ${
                        isActive
                          ? "bg-surface text-ink font-semibold border border-hairline shadow-2xs"
                          : "text-ink-muted hover:text-ink hover:bg-surface border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <ChatCircleText
                          size={14}
                          className={`shrink-0 ${
                            isActive
                              ? "text-primary-brand"
                              : "text-ink-muted"
                          }`}
                        />
                        <span className="truncate">{conv.title}</span>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => onDeleteConversation(conv.id, e)}
                        title="Delete conversation"
                        className="opacity-0 group-hover:opacity-100 p-1 text-ink-muted hover:text-rose-500 transition-opacity"
                      >
                        <Trash size={12} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer info, theme toggle, and logout */}
        <div className="p-3 border-t border-hairline space-y-2 text-xs">
          <div className="px-2 py-1.5 rounded-lg bg-surface flex flex-col justify-center border border-hairline text-ink-muted">
            <span className="text-[11px] font-semibold text-ink truncate" title={email || ""}>
              {username}
            </span>
            <span className="text-[10px] uppercase tracking-wider truncate" title={email || ""}>
              {organization}
            </span>
          </div>

          <button
            type="button"
            onClick={onToggleDarkMode}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl border border-hairline bg-surface text-ink hover:bg-surface-elevated transition-colors shadow-2xs"
          >
            <span className="flex items-center gap-2">
              {darkMode ? (
                <Moon size={15} className="text-accent-gold" />
              ) : (
                <Sun size={15} className="text-accent-gold" />
              )}
              <span>{darkMode ? "Dark Mode" : "Light Mode"}</span>
            </span>
            <span className="text-[11px] text-ink-muted font-mono font-medium">
              {darkMode ? "ON" : "OFF"}
            </span>
          </button>

          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="w-full flex items-center justify-between px-3 py-2 rounded-xl border border-hairline bg-surface text-ink hover:text-rose-600 dark:hover:text-rose-400 hover:border-rose-500/30 transition-colors shadow-2xs"
            >
              <span className="flex items-center gap-2">
                <SignOut size={15} className="text-ink-muted" />
                <span>Log Out</span>
              </span>
            </button>
          )}
        </div>
      </aside>
    </>
  );
};

export default ChatSidebar;
