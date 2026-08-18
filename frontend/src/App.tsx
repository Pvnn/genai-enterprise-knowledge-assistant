/**
 * Root application component – wires routing between Auth, Chat, and Upload.
 * Owner: P7
 */
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./auth/Login";
import ChatPage from "./chat/ChatPage";
import UploadPage from "./upload/UploadPage";

// TODO(P6): Replace this direct localStorage read with a proper auth context / hook
// (e.g. useAuth()) once the P6 auth module implements one.
const currentUserRole = () => localStorage.getItem("user_role") || "member";
const isLoggedIn = () => Boolean(localStorage.getItem("access_token"));

const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const RequireAdmin: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }
  if (currentUserRole() !== "admin") {
    return <div>Access Denied. Admins only.</div>;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/chat"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/upload"
          element={
            <RequireAdmin>
              <UploadPage />
            </RequireAdmin>
          }
        />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;