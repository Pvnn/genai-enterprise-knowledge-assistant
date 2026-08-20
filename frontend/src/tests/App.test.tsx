/**
 * Unit tests for App.tsx (Root routing & auth guard).
 * Owner: P7
 *
 * Tests:
 *   - Unauthenticated user navigating to /chat is redirected to /login and sees Login component
 *   - Unauthenticated user navigating to /upload is redirected to /login and sees Login component
 *   - Unauthenticated user on /login sees Login component
 *   - Unauthenticated user on /register sees Register component (public route)
 *   - Authenticated user on /chat sees ChatPage
 *   - Authenticated admin user on /upload sees UploadPage
 *   - Authenticated non-admin user on /upload sees Access Restricted
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import App from "../App";

vi.mock("../chat/ChatPage", () => ({
  default: () => <div data-testid="chat-page">Chat Workspace</div>,
}));

vi.mock("../upload/UploadPage", () => ({
  default: () => <div data-testid="upload-page">Upload Document Page</div>,
}));

vi.mock("../auth/Login", () => ({
  default: () => <div data-testid="login-page">Login Page Component</div>,
}));

vi.mock("../auth/Register", () => ({
  default: () => <div data-testid="register-page">Register Page Component</div>,
}));

describe("App.tsx Auth Guard & Routing", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    window.history.pushState({}, "", "/chat");
  });

  it("redirects unauthenticated users on protected route /chat to /login", () => {
    const replaceSpy = vi.spyOn(window.history, "replaceState");

    render(<App />);

    expect(replaceSpy).toHaveBeenCalledWith({}, "", "/login");
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated users on protected route /upload to /login", () => {
    window.history.pushState({}, "", "/upload");
    const replaceSpy = vi.spyOn(window.history, "replaceState");

    render(<App />);

    expect(replaceSpy).toHaveBeenCalledWith({}, "", "/login");
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("upload-page")).not.toBeInTheDocument();
  });

  it("renders Login page directly when path is /login", () => {
    window.history.pushState({}, "", "/login");

    render(<App />);

    expect(screen.getByTestId("login-page")).toBeInTheDocument();
  });

  it("renders Register page directly without access_token when path is /register", () => {
    window.history.pushState({}, "", "/register");
    const replaceSpy = vi.spyOn(window.history, "replaceState");

    render(<App />);

    expect(replaceSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId("register-page")).toBeInTheDocument();
    expect(screen.queryByTestId("login-page")).not.toBeInTheDocument();
  });

  it("renders ChatPage for authenticated users on /chat", () => {
    localStorage.setItem("access_token", "valid-jwt-token");
    window.history.pushState({}, "", "/chat");

    render(<App />);

    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.queryByTestId("login-page")).not.toBeInTheDocument();
  });

  it("renders UploadPage for authenticated admin users on /upload", () => {
    localStorage.setItem("access_token", "admin-jwt-token");
    localStorage.setItem("user_role", "admin");
    window.history.pushState({}, "", "/upload");

    render(<App />);

    expect(screen.getByTestId("upload-page")).toBeInTheDocument();
  });

  it("renders Access Restricted for authenticated non-admin users on /upload", () => {
    localStorage.setItem("access_token", "member-jwt-token");
    localStorage.setItem("user_role", "member");
    window.history.pushState({}, "", "/upload");

    render(<App />);

    expect(screen.getByText("Access Restricted")).toBeInTheDocument();
    expect(screen.queryByTestId("upload-page")).not.toBeInTheDocument();
  });
});
