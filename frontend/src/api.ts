import type { Account, TrackSegment } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

type LoginResponse = {
  accessToken: string;
  tokenType: string;
  account: Account;
};

type ApiOptions = {
  method?: string;
  token?: string;
  body?: unknown;
};

async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers: HeadersInit = {};
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof data?.detail === "string" ? data.detail : "请求失败";
    throw new Error(message);
  }
  return data as T;
}

export function fetchHealth(): Promise<{ status: string; database: string }> {
  return apiRequest("/health");
}

export function register(username: string, password: string): Promise<Account> {
  return apiRequest("/auth/register", {
    method: "POST",
    body: { username, password },
  });
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return apiRequest("/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export function fetchMe(token: string): Promise<Account> {
  return apiRequest("/auth/me", { token });
}

export function fetchSegments(token: string): Promise<TrackSegment[]> {
  return apiRequest("/segments", { token });
}

export function importFlight(
  token: string,
  body: { flightNumber: string; date: string },
): Promise<TrackSegment> {
  return apiRequest("/import/flight", {
    method: "POST",
    token,
    body,
  });
}

export function importTrain(
  token: string,
  body: {
    trainCode: string;
    date: string;
    fromStation: string;
    toStation: string;
  },
): Promise<TrackSegment> {
  return apiRequest("/import/train", {
    method: "POST",
    token,
    body,
  });
}
