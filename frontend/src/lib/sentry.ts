const REDACTED = "[REDACTED]";
const SENSITIVE_KEYWORDS = [
  "authorization",
  "cookie",
  "password",
  "passwd",
  "token",
  "api_key",
  "apikey",
  "api-key",
  "secret",
  "key",
];

export function isSensitiveKey(key: string) {
  const normalized = key.toLowerCase().replaceAll("-", "_");

  return SENSITIVE_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

export function sanitizeSentryValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeSentryValue(item));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        isSensitiveKey(key) ? REDACTED : sanitizeSentryValue(item),
      ]),
    );
  }

  return value;
}

export function sentryBeforeSend<T>(event: T): T {
  return sanitizeSentryValue(event) as T;
}
