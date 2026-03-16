import { clearSessionWrappingKey } from "./chatCrypto";
import { queryClient } from "./queryClient";
import { useAuthStore } from "../store/auth";

export function clearAuthSession(options?: { redirectToLogin?: boolean }) {
  localStorage.removeItem("pcm_access_token");
  localStorage.removeItem("pcm_refresh_token");
  clearSessionWrappingKey();
  useAuthStore.getState().setUser(null);
  queryClient.clear();

  if (!options?.redirectToLogin) {
    return;
  }

  if (window.location.pathname !== "/login") {
    window.location.replace("/login");
  }
}
