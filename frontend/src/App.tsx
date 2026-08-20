/**
 * Root application component. Wires routing between Auth, Chat, and Upload.
 * Owner: P7
 */

import React, { useState, useEffect } from "react";
import ChatPage from "./chat/ChatPage";
import Login from "./auth/Login";
import Register from "./auth/Register";
import UploadPage from "./upload/UploadPage";

export const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // TODO: confirm with P6 whether auth/* already exposes these via a hook or context.
  const currentUserRole = localStorage.getItem("user_role") || "member";

  const handleLogout = () => {
    // TODO: Delegate to P6 auth module (e.g. useAuth().logout()) once P6 exposes a logout function/hook.
    localStorage.removeItem("access_token");
    localStorage.removeItem("tenant_id");
    localStorage.removeItem("user_role");
    localStorage.removeItem("user_id");
    localStorage.removeItem("genai_assistant_conversations");
    window.history.pushState({}, "", "/login");
    setCurrentPath("/login");
  };

  // Auth guard: /login and /register are public; all other routes require access_token
  if (currentPath !== "/login" && currentPath !== "/register" && !localStorage.getItem("access_token")) {
    window.history.replaceState({}, "", "/login");
    return <Login />;
  }

  if (currentPath === "/login") {
    return (
      <Login
        onNavigateRegister={() => {
          window.history.pushState({}, "", "/register");
          setCurrentPath("/register");
        }}
        onLoginSuccess={() => {
          window.history.pushState({}, "", "/chat");
          setCurrentPath("/chat");
        }}
      />
    );
  }

  if (currentPath === "/register") {
    return (
      <Register
        onNavigateLogin={() => {
          window.history.pushState({}, "", "/login");
          setCurrentPath("/login");
        }}
      />
    );
  }

  if (currentPath === "/upload") {
    if (currentUserRole !== "admin") {
      return (
        <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200">
          <div className="text-center p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
            <h2 className="text-base font-bold mb-2">Access Restricted</h2>
            <p className="text-xs text-slate-500 mb-4">
              Document upload is restricted to administrative personnel.
            </p>
            <button
              type="button"
              onClick={() => {
                window.history.pushState({}, "", "/chat");
                setCurrentPath("/chat");
              }}
              className="px-4 py-2 text-xs font-medium rounded-xl bg-sky-600 hover:bg-sky-700 text-white transition-colors"
            >
              Return to Chat
            </button>
          </div>
        </div>
      );
    }
    return (
      <UploadPage
        onNavigateBack={() => {
          window.history.pushState({}, "", "/chat");
          setCurrentPath("/chat");
        }}
      />
    );
  }

  return (
    <ChatPage
      onLogout={handleLogout}
      userRole={currentUserRole}
      onNavigateUpload={() => {
        window.history.pushState({}, "", "/upload");
        setCurrentPath("/upload");
      }}
    />
  );
};

export default App;
