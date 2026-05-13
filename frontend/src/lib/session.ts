import { env } from "@/lib/env";

const ACCESS_TOKEN_KEY = "access_token";
const TOKEN_TYPE_KEY = "token_type";
const ACCESS_TOKEN_EXPIRES_AT_KEY = "access_token_expires_at";
const CURRENT_USER_KEY = "current_user";
const REFRESH_BUFFER_MS = 10 * 1000;

type LoginEnvelope = {
  code: number;
  msg: string;
  data: {
    access_token: string;
    token_type: string;
    expires_in: number;
  };
};

type StoredCurrentUser = {
  username?: string | null;
  email?: string | null;
};

let refreshPromise: Promise<string | null> | null = null;
let restorePromise: Promise<boolean> | null = null;
let isRedirectingToLogin = false;

export function hasStoredSession() {
  if (!isBrowser()) {
    return false;
  }

  const accessToken = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  const currentUser = window.localStorage.getItem(CURRENT_USER_KEY);

  return Boolean(accessToken && currentUser);
}

export function getAccessToken() {
  if (!isBrowser()) {
    return null;
  }

  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getTokenType() {
  if (!isBrowser()) {
    return null;
  }

  return window.localStorage.getItem(TOKEN_TYPE_KEY);
}

export function getAccessTokenExpiresAt() {
  if (!isBrowser()) {
    return null;
  }

  const value = window.localStorage.getItem(ACCESS_TOKEN_EXPIRES_AT_KEY);

  if (!value) {
    return null;
  }

  const expiresAt = Number(value);

  return Number.isFinite(expiresAt) ? expiresAt : null;
}

export function isAccessTokenExpiringSoon(bufferMs = REFRESH_BUFFER_MS) {
  const expiresAt = getAccessTokenExpiresAt();

  if (!expiresAt) {
    return true;
  }

  return expiresAt - Date.now() <= bufferMs;
}

export function setSessionTokens({
  accessToken,
  tokenType,
  expiresIn,
}: {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
}) {
  if (!isBrowser()) {
    return;
  }

  const expiresAt = Date.now() + expiresIn * 1000;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(TOKEN_TYPE_KEY, tokenType);
  window.localStorage.setItem(ACCESS_TOKEN_EXPIRES_AT_KEY, String(expiresAt));
}

export function setStoredCurrentUser(currentUser: unknown) {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(currentUser));
}

export function getStoredCurrentUser(): StoredCurrentUser | null {
  if (!isBrowser()) {
    return null;
  }

  const rawCurrentUser = window.localStorage.getItem(CURRENT_USER_KEY);

  if (!rawCurrentUser) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawCurrentUser) as unknown;

    if (parsed && typeof parsed === "object") {
      return parsed as StoredCurrentUser;
    }
  } catch {
    return null;
  }

  return null;
}

export function clearSession() {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(TOKEN_TYPE_KEY);
  window.localStorage.removeItem(ACCESS_TOKEN_EXPIRES_AT_KEY);
  window.localStorage.removeItem(CURRENT_USER_KEY);
}

export function handleUnauthorizedSession() {
  clearSession();
  redirectToLogin();
}

export async function getValidAccessToken() {
  const accessToken = getAccessToken();

  if (!accessToken) {
    return refreshAccessToken();
  }

  if (!isAccessTokenExpiringSoon()) {
    return accessToken;
  }

  return refreshAccessToken();
}

export async function refreshAccessToken() {
  if (!isBrowser()) {
    return null;
  }

  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch(buildUrl("/auth/refresh-token"), {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        handleUnauthorizedSession();
        return null;
      }

      const payload = (await parseJson<LoginEnvelope>(response)) ?? null;

      if (!payload?.data) {
        handleUnauthorizedSession();
        return null;
      }

      setSessionTokens({
        accessToken: payload.data.access_token,
        tokenType: payload.data.token_type,
        expiresIn: payload.data.expires_in,
      });

      return payload.data.access_token;
    } catch {
      handleUnauthorizedSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function restoreSession() {
  if (!isBrowser()) {
    return false;
  }

  if (hasStoredSession() && !isAccessTokenExpiringSoon()) {
    return true;
  }

  if (restorePromise) {
    return restorePromise;
  }

  restorePromise = (async () => {
    const accessToken = await getValidAccessToken();

    if (!accessToken) {
      handleUnauthorizedSession();
      return false;
    }

    try {
      const response = await fetch(buildUrl("/users"), {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        credentials: "include",
      });

      if (!response.ok) {
        handleUnauthorizedSession();
        return false;
      }

      const payload = (await parseJson<{ code: number; msg: string; data: unknown }>(response)) ?? null;

      if (!payload?.data) {
        handleUnauthorizedSession();
        return false;
      }

      setStoredCurrentUser(payload.data);
      return true;
    } catch {
      handleUnauthorizedSession();
      return false;
    } finally {
      restorePromise = null;
    }
  })();

  return restorePromise;
}

function buildUrl(path: string) {
  return `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json() as Promise<T>;
}

function isBrowser() {
  return typeof window !== "undefined";
}

function redirectToLogin() {
  if (!isBrowser() || isRedirectingToLogin) {
    return;
  }

  const { pathname } = window.location;

  if (pathname.startsWith("/auth/")) {
    return;
  }

  isRedirectingToLogin = true;
  window.location.replace("/auth/login");
}
