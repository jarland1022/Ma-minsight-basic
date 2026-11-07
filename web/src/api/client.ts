import axios, { isAxiosError } from "axios";

const TOKEN_KEY = "ma_minsight_token";
export const SESSION_EXPIRED_KEY = "ma_minsight_session_expired";

export const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (isAxiosError(error) && error.response?.status === 401) {
      const path = window.location.pathname;
      if (!path.startsWith("/login")) {
        clearToken();
        sessionStorage.setItem(SESSION_EXPIRED_KEY, "1");
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  },
);

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  sessionStorage.removeItem(SESSION_EXPIRED_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function logout() {
  clearToken();
  window.location.href = "/login";
}

export type LoginResult = {
  access_token?: string | null;
  token_type?: string;
  user?: Record<string, unknown> | null;
  mfa_required?: boolean;
  mfa_setup_required?: boolean;
  mfa_token?: string | null;
  mfa_secret?: string | null;
  otpauth_uri?: string | null;
  qr_png_data_url?: string | null;
  must_change_password?: boolean;
  token_class?: string | null;
  changed?: boolean;
};

export async function login(username: string, password: string): Promise<LoginResult> {
  const { data } = await api.post<LoginResult>("/auth/login", { username, password });
  if (data.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function verifyMfa(mfaToken: string, code: string): Promise<LoginResult> {
  const { data } = await api.post<LoginResult>("/auth/mfa/verify", {
    mfa_token: mfaToken,
    code,
  });
  if (data.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<LoginResult> {
  const { data } = await api.post<LoginResult>("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  if (data.access_token) {
    setToken(data.access_token);
  } else if (data.mfa_setup_required || data.mfa_required) {
    // Password changed; awaiting MFA — drop bootstrap token until MFA completes.
    clearToken();
  }
  return data;
}

/** Extract FastAPI error detail for display in the UI. */
export function formatApiError(error: unknown): string {
  if (!isAxiosError(error)) {
    return error instanceof Error ? error.message : "未知错误";
  }
  const status = error.response?.status;
  const detail = error.response?.data?.detail;
  if (status === 403) {
    return "需要管理员账号才能手动运行（请使用 admin 登录）";
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
      .join("；");
  }
  if (error.message === "Network Error") {
    return "网络错误或网关超时，请稍后重试";
  }
  return status ? `请求失败 (HTTP ${status})` : "请求失败";
}
