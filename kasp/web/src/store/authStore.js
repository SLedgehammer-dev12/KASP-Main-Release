/**
 * KASP Auth Store
 * Manages authenticated user state, permissions, and active session tokens.
 */

import { createStore } from "./store.js";
import { api } from "../api/client.js";

const ROLE_PERMISSIONS = {
  admin: ["read", "write", "delete", "export", "config", "manage_users"],
  engineer: ["read", "write", "export"],
  user: ["read", "export"],
  viewer: ["read"],
};

export const authStore = createStore({
  isAuthenticated: false,
  user: null,
  role: "guest",
  permissions: ["read"],
  csrfToken: "",
  loading: true,
});

export async function checkSession() {
  authStore.setState({ loading: true });
  try {
    const data = await api.get("/api/v1/auth/me");
    if (data && data.user) {
      const role = data.user.role || "user";
      api.setCsrfToken(data.csrf_token);
      authStore.setState({
        isAuthenticated: true,
        user: data.user,
        role: role,
        permissions: ROLE_PERMISSIONS[role] || ["read"],
        csrfToken: data.csrf_token,
        loading: false,
      });
      return true;
    }
  } catch (err) {
    authStore.setState({
      isAuthenticated: false,
      user: null,
      role: "guest",
      permissions: ["read"],
      loading: false,
    });
  }
  return false;
}

export async function loginUser(username, password) {
  const data = await api.post("/api/v1/auth/login", { username, password });
  if (data && data.user) {
    const role = data.user.role || "user";
    api.setAuthToken(data.token);
    api.setCsrfToken(data.csrf_token);
    authStore.setState({
      isAuthenticated: true,
      user: data.user,
      role: role,
      permissions: ROLE_PERMISSIONS[role] || ["read"],
      csrfToken: data.csrf_token,
      loading: false,
    });
    return data;
  }
  throw new Error("Giriş yapılamadı.");
}

export async function logoutUser() {
  try {
    await api.post("/api/v1/auth/logout");
  } catch (_) {}
  api.setAuthToken("");
  api.setCsrfToken("");
  authStore.setState({
    isAuthenticated: false,
    user: null,
    role: "guest",
    permissions: ["read"],
    csrfToken: "",
  });
}

export function hasPermission(perm) {
  const state = authStore.getState();
  return state.permissions.includes(perm) || state.role === "admin";
}
