import axios from "axios";

import { clearAuthSession } from "../lib/session";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("pcm_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshRequest: Promise<string | null> | null = null;

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("pcm_refresh_token");
  if (!refreshToken) {
    clearAuthSession({ redirectToLogin: true });
    return null;
  }

  if (!refreshRequest) {
    refreshRequest = axios
      .post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
      .then((response) => {
        const nextAccessToken = response.data?.access_token;
        const nextRefreshToken = response.data?.refresh_token;
        if (!nextAccessToken || !nextRefreshToken) {
          clearAuthSession({ redirectToLogin: true });
          return null;
        }

        localStorage.setItem("pcm_access_token", nextAccessToken);
        localStorage.setItem("pcm_refresh_token", nextRefreshToken);
        return nextAccessToken;
      })
      .catch(() => {
        clearAuthSession({ redirectToLogin: true });
        return null;
      })
      .finally(() => {
        refreshRequest = null;
      });
  }

  return refreshRequest;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const originalRequest = error?.config;
    const requestUrl = String(originalRequest?.url || "");
    const isLoginRequest = requestUrl.includes("/auth/login");
    const isRefreshRequest = requestUrl.includes("/auth/refresh");
    const alreadyRetried = Boolean(originalRequest?._retry);

    if (status !== 401 || !originalRequest || isLoginRequest) {
      return Promise.reject(error);
    }

    if (isRefreshRequest || alreadyRetried) {
      clearAuthSession({ redirectToLogin: true });
      return Promise.reject(error);
    }

    originalRequest._retry = true;
    const nextAccessToken = await refreshAccessToken();
    if (!nextAccessToken) {
      return Promise.reject(error);
    }

    originalRequest.headers = originalRequest.headers || {};
    originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
    return api(originalRequest);
  }
);

export default api;
