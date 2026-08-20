/**
 * AdminDashboard Main Container.
 * Claude-inspired aesthetic with multi-tenant isolation, rich analytics, document controls, and member management.
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  ChartLineUp,
  Files,
  Users,
  BookOpen,
  ChatCircleDots,
  Sun,
  Moon,
  SignOut,
  Buildings,
  Copy,
  Check,
  ShieldCheck,
  Shield,
  ArrowSquareOut,
} from "@phosphor-icons/react";
import {
  AdminAnalyticsData,
  AdminDocument,
  AdminUser,
  GlossaryEntry,
} from "./types";
import {
  fetchAdminAnalytics,
  fetchAdminDocuments,
  updateAdminDocument,
  deleteAdminDocument,
  fetchAdminUsers,
  createAdminUser,
  updateAdminUserRole,
  deleteAdminUser,
  fetchAdminGlossary,
  addGlossaryTerm,
  deleteGlossaryTerm,
} from "../api/client";
import AnalyticsTab from "./components/AnalyticsTab";
import DocumentsTab from "./components/DocumentsTab";
import MembersTab from "./components/MembersTab";
import GlossaryTab from "./components/GlossaryTab";

type AdminTab = "analytics" | "documents" | "members" | "glossary";

interface AdminDashboardProps {
  onReturnToChat: () => void;
  onLogout?: () => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  onReturnToChat,
  onLogout,
}) => {
  const [activeTab, setActiveTab] = useState<AdminTab>(() => {
    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get("tab");
    if (tabParam === "documents" || tabParam === "members" || tabParam === "glossary") {
      return tabParam;
    }
    return "analytics";
  });

  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return document.documentElement.classList.contains("dark");
  });

  const [copiedTenant, setCopiedTenant] = useState(false);

  const tenantId = localStorage.getItem("tenant_id") || "00000000-0000-0000-0000-000000000001";
  const currentUserId = localStorage.getItem("user_id") || "";

  // Data States
  const [analyticsData, setAnalyticsData] = useState<AdminAnalyticsData | null>(null);
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);

  // Loading States
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingGlossary, setLoadingGlossary] = useState(true);

  // Sync Dark Mode
  const handleToggleDarkMode = () => {
    setDarkMode((prev) => {
      const next = !prev;
      if (next) {
        document.documentElement.classList.add("dark");
        localStorage.setItem("genai_assistant_theme", "dark");
      } else {
        document.documentElement.classList.remove("dark");
        localStorage.setItem("genai_assistant_theme", "light");
      }
      return next;
    });
  };

  const loadAnalytics = useCallback(async () => {
    setLoadingAnalytics(true);
    try {
      const data = await fetchAdminAnalytics();
      setAnalyticsData(data);
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const docs = await fetchAdminDocuments();
      setDocuments(docs);
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const u = await fetchAdminUsers();
      setUsers(u);
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  const loadGlossary = useCallback(async () => {
    setLoadingGlossary(true);
    try {
      const g = await fetchAdminGlossary();
      setGlossary(g);
    } finally {
      setLoadingGlossary(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
    loadDocuments();
    loadUsers();
    loadGlossary();
  }, [loadAnalytics, loadDocuments, loadUsers, loadGlossary]);

  const handleCopyTenantId = () => {
    navigator.clipboard.writeText(tenantId);
    setCopiedTenant(true);
    setTimeout(() => setCopiedTenant(false), 2000);
  };

  const handleTabChange = (tab: AdminTab) => {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    window.history.replaceState({}, "", url.toString());
  };

  // Handlers for Document Updates
  const handleUpdateDocument = async (docId: string, updates: Partial<AdminDocument>) => {
    const updated = await updateAdminDocument(docId, updates);
    setDocuments((prev) => prev.map((d) => (d.id === docId ? updated : d)));
  };

  const handleDeleteDocument = async (docId: string) => {
    await deleteAdminDocument(docId);
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
    loadAnalytics();
  };

  // Handlers for Users
  const handleCreateUser = async (data: { email: string; password: string; role: string }) => {
    const newUser = await createAdminUser(data);
    setUsers((prev) => [...prev, newUser]);
    loadAnalytics();
  };

  const handleUpdateUserRole = async (userId: string, role: string) => {
    const updated = await updateAdminUserRole(userId, role);
    setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
  };

  const handleDeleteUser = async (userId: string) => {
    await deleteAdminUser(userId);
    setUsers((prev) => prev.filter((u) => u.id !== userId));
    loadAnalytics();
  };

  // Handlers for Glossary
  const handleAddGlossary = async (term: string, expansion: string) => {
    const newEntry = await addGlossaryTerm(term, expansion);
    setGlossary((prev) => {
      const idx = prev.findIndex((g) => g.term.toUpperCase() === newEntry.term.toUpperCase());
      if (idx !== -1) {
        const copy = [...prev];
        copy[idx] = newEntry;
        return copy;
      }
      return [...prev, newEntry];
    });
  };

  const handleDeleteGlossary = async (term: string) => {
    await deleteGlossaryTerm(term);
    setGlossary((prev) => prev.filter((g) => g.term.toUpperCase() !== term.toUpperCase()));
  };

  return (
    <div className="min-h-screen bg-canvas text-ink flex flex-col transition-colors duration-200">
      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-surface/80 backdrop-blur-md border-b border-hairline px-4 sm:px-8 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Brand & Organization */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-primary-brand text-white flex items-center justify-center shadow-xs">
            <ShieldCheck size={22} weight="bold" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-ink tracking-tight">
                Enterprise Admin Center
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-accent-gold/15 text-accent-gold border border-accent-gold/30 uppercase tracking-wider">
                Admin Role
              </span>
            </div>
            {/* Tenant ID Badge */}
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[11px] text-ink-muted">Tenant:</span>
              <button
                type="button"
                onClick={handleCopyTenantId}
                className="inline-flex items-center gap-1 font-mono text-[11px] text-ink-muted hover:text-ink px-1.5 py-0.5 rounded bg-surface-muted border border-hairline transition-colors"
                title="Click to copy full tenant ID"
              >
                <span>{tenantId.slice(0, 14)}...</span>
                {copiedTenant ? (
                  <Check size={11} className="text-emerald-500 font-bold" />
                ) : (
                  <Copy size={11} />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Side Navigation Actions */}
        <div className="flex items-center gap-2">
          {/* Return to Chat Button */}
          <button
            type="button"
            onClick={onReturnToChat}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted transition-colors shadow-2xs"
          >
            <ChatCircleDots size={16} className="text-primary-brand" weight="bold" />
            <span>Return to Chat</span>
          </button>

          {/* Theme Toggle */}
          <button
            type="button"
            onClick={handleToggleDarkMode}
            className="p-2 rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted transition-colors shadow-2xs"
            title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {darkMode ? (
              <Moon size={16} className="text-accent-gold" />
            ) : (
              <Sun size={16} className="text-accent-gold" />
            )}
          </button>

          {/* Logout */}
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="p-2 rounded-xl bg-surface border border-hairline text-ink hover:text-rose-600 hover:border-rose-500/30 transition-colors shadow-2xs"
              title="Log Out"
            >
              <SignOut size={16} />
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area with Sub-Tabs */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-8 py-6 space-y-6">
        {/* Navigation Tabs Bar */}
        <div className="flex items-center gap-1.5 p-1.5 rounded-2xl bg-surface-muted border border-hairline overflow-x-auto">
          <button
            type="button"
            onClick={() => handleTabChange("analytics")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "analytics"
                ? "bg-surface text-ink shadow-2xs border border-hairline"
                : "text-ink-muted hover:text-ink hover:bg-surface/50"
            }`}
          >
            <ChartLineUp size={16} className={activeTab === "analytics" ? "text-primary-brand" : "text-ink-muted"} />
            <span>Overview & Analytics</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange("documents")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "documents"
                ? "bg-surface text-ink shadow-2xs border border-hairline"
                : "text-ink-muted hover:text-ink hover:bg-surface/50"
            }`}
          >
            <Files size={16} className={activeTab === "documents" ? "text-accent-gold" : "text-ink-muted"} />
            <span>Document Management</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-surface-muted text-ink-muted font-mono">
              {documents.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange("members")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "members"
                ? "bg-surface text-ink shadow-2xs border border-hairline"
                : "text-ink-muted hover:text-ink hover:bg-surface/50"
            }`}
          >
            <Users size={16} className={activeTab === "members" ? "text-primary-brand" : "text-ink-muted"} />
            <span>Enterprise Members</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-surface-muted text-ink-muted font-mono">
              {users.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange("glossary")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "glossary"
                ? "bg-surface text-ink shadow-2xs border border-hairline"
                : "text-ink-muted hover:text-ink hover:bg-surface/50"
            }`}
          >
            <BookOpen size={16} className={activeTab === "glossary" ? "text-accent-gold" : "text-ink-muted"} />
            <span>Glossary & Terminology</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-surface-muted text-ink-muted font-mono">
              {glossary.length}
            </span>
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === "analytics" && (
          <AnalyticsTab
            data={analyticsData}
            loading={loadingAnalytics}
            onRefresh={loadAnalytics}
          />
        )}

        {activeTab === "documents" && (
          <DocumentsTab
            documents={documents}
            loading={loadingDocs}
            onRefresh={loadDocuments}
            onUpdateDocument={handleUpdateDocument}
            onDeleteDocument={handleDeleteDocument}
          />
        )}

        {activeTab === "members" && (
          <MembersTab
            users={users}
            currentUserId={currentUserId}
            loading={loadingUsers}
            onRefresh={loadUsers}
            onCreateUser={handleCreateUser}
            onUpdateUserRole={handleUpdateUserRole}
            onDeleteUser={handleDeleteUser}
          />
        )}

        {activeTab === "glossary" && (
          <GlossaryTab
            entries={glossary}
            loading={loadingGlossary}
            onRefresh={loadGlossary}
            onAddTerm={handleAddGlossary}
            onDeleteTerm={handleDeleteGlossary}
          />
        )}
      </main>
    </div>
  );
};

export default AdminDashboard;
