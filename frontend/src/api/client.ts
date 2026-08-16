/**
 * Typed API client for the backend.
 * Owner: P7
 *
 * Implements:
 *   - POST /auth/login
 *   - GET  /auth/me
 *   - POST /chat  (SSE stream)
 *   - POST /feedback
 *
 * All request/response shapes must match Section 5 of the engineering spec.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// TODO P7: implement typed fetch helpers and SSE streaming for /chat
export { API_BASE };
