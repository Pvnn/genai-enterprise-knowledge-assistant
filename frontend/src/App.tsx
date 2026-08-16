/**
 * Root application component – wires routing between Auth and Chat.
 * Owner: P7
 */
import React from "react";
import UploadPage from "./upload/UploadPage";

// TODO P7: implement proper router (e.g. react-router-dom) between /login, /chat, and /upload
// This is a minimal placeholder showing how the role routes to the upload page.
const App: React.FC = () => {
  // TODO(P6): Replace this direct localStorage read with a proper auth context / hook (e.g., useAuth())
  // once the P6 auth module implements one. This is a stopgap for the upload routing.
  const currentUserRole = localStorage.getItem("user_role") || "member";
  
  // Basic routing stub
  const path = window.location.pathname;
  if (path === "/upload") {
    if (currentUserRole !== "admin") {
      return <div>Access Denied. Admins only.</div>; // Or redirect to /chat
    }
    return <UploadPage />;
  }

  return <div>GenAI Enterprise Knowledge Assistant</div>;
};

export default App;
