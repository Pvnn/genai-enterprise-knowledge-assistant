/**
 * Root application component. Wires routing between Auth, Chat, Admin Dashboard, and Upload.
 */

import React, { useState, useEffect } from "react";
import ChatPage from "./chat/ChatPage";
import Login from "./auth/Login";
import { Register } from "./auth/Register";
import UploadPage from "./upload/UploadPage";
import AdminDashboard from "./admin/AdminDashboard";
import { ShieldCheck } from "@phosphor-icons/react";

export const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  const navigateTo = (path: string) => {
    window.history.pushState({}, "", path);
    setCurrentPath(path);
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("tenant_id");
    localStorage.removeItem("user_role");
    localStorage.removeItem("user_id");
    localStorage.removeItem("genai_assistant_conversations");
    window.history.pushState({}, "", "/login");
    setCurrentPath("/login");
  };

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);

    const handleAuthError = () => handleLogout();
    window.addEventListener("auth_error", handleAuthError);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      window.removeEventListener("auth_error", handleAuthError);
    };
  }, []);

  const currentUserRole = localStorage.getItem("user_role") || "member";

  // Auth guard: /login and /register are public; all other routes require access_token
  if (currentPath !== "/login" && currentPath !== "/register" && !localStorage.getItem("access_token")) {
    window.history.replaceState({}, "", "/login");
    return (
      <Login
        onNavigateRegister={() => navigateTo("/register")}
        onLoginSuccess={() => navigateTo("/chat")}
      />
    );
  }

  if (currentPath === "/login") {
    return (
      <Login
        onNavigateRegister={() => navigateTo("/register")}
        onLoginSuccess={() => navigateTo("/chat")}
      />
    );
  }

  if (currentPath === "/register") {
    return (
      <Register
        onNavigateLogin={() => navigateTo("/login")}
      />
    );
  }

  // Admin Dashboard Route
  if (currentPath === "/admin") {
    if (currentUserRole !== "admin") {
      return (
        <div className="flex h-screen items-center justify-center bg-canvas text-ink px-4">
          <div className="text-center p-8 bg-surface border border-hairline rounded-3xl shadow-sm max-w-sm w-full space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 mx-auto flex items-center justify-center">
              <ShieldCheck size={24} weight="bold" />
            </div>
            <div>
              <h2 className="text-base font-bold text-ink">Administrative Access Restricted</h2>
              <p className="text-xs text-ink-muted mt-1">
                The Enterprise Admin Dashboard and document management controls are restricted to administrators.
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigateTo("/chat")}
              className="w-full py-2.5 px-4 text-xs font-semibold rounded-xl bg-primary-brand text-white hover:opacity-90 transition-all shadow-2xs"
            >
              Return to Chat Workspace
            </button>
          </div>
        </div>
      );
    }
    return (
      <AdminDashboard
        onReturnToChat={() => navigateTo("/chat")}
        onLogout={handleLogout}
      />
    );
  }

  if (currentPath === "/upload") {
    if (currentUserRole !== "admin") {
      return (
        <div className="flex h-screen items-center justify-center bg-canvas text-ink px-4">
          <div className="text-center p-8 bg-surface border border-hairline rounded-3xl shadow-sm max-w-sm w-full space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 mx-auto flex items-center justify-center">
              <ShieldCheck size={24} weight="bold" />
            </div>
            <div>
              <h2 className="text-base font-bold text-ink">Administrative Access Restricted</h2>
              <p className="text-xs text-ink-muted mt-1">
                Document ingestion and upload is restricted to administrators.
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigateTo("/chat")}
              className="w-full py-2.5 px-4 text-xs font-semibold rounded-xl bg-primary-brand text-white hover:opacity-90 transition-all shadow-2xs"
            >
              Return to Chat Workspace
            </button>
          </div>
        </div>
      );
    }
    return (
      <UploadPage
        onNavigateBack={() => navigateTo("/chat")}
      />
    );
  }

  return (
    <ChatPage
      onLogout={handleLogout}
      userRole={currentUserRole}
      onNavigateUpload={() => navigateTo("/admin")}
    />
  );
};

export default App;
