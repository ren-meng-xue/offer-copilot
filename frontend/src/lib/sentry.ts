import * as Sentry from "@sentry/nextjs";

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
];

const NON_SENSITIVE_KEYWORDS = [
  "tokenizer",
  "vector",
  "chunk",
  "keyboard",
  "hotkey",
  "keymap",
];

const EMAIL_REGEX = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;
const SENSITIVE_ASSIGN_REGEX = /(authorization|cookie|password|passwd|token|api_key|secret|private_key|secret_key)[\s:=\'\"]+([^\s\'\",&]+)/gi;

export function isSensitiveKey(key: string): boolean {
  const normalized = key.toLowerCase().replaceAll("-", "_");

  if (NON_SENSITIVE_KEYWORDS.some((ns) => normalized.includes(ns))) {
    return false;
  }

  if (SENSITIVE_KEYWORDS.some((keyword) => normalized.includes(keyword))) {
    return true;
  }

  if (normalized.includes("key")) {
    return true;
  }

  return false;
}

export function sanitizeString(val: string): string {
  let sanitized = val.replace(EMAIL_REGEX, "[EMAIL_REDACTED]");
  sanitized = sanitized.replace(SENSITIVE_ASSIGN_REGEX, "$1=[REDACTED]");
  return sanitized;
}

export function sanitizeSentryValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeSentryValue(item));
  }

  if (typeof value === "string") {
    return sanitizeString(value);
  }

  if (value && typeof value === "object") {
    try {
      return Object.fromEntries(
        Object.entries(value).map(([key, item]) => [
          key,
          isSensitiveKey(key) ? REDACTED : sanitizeSentryValue(item),
        ]),
      );
    } catch {
      return value;
    }
  }

  return value;
}

export function sentryBeforeSend<T>(event: T): T {
  return sanitizeSentryValue(event) as T;
}

export function initSentry(options: {
  dsn: string | undefined;
  environment: string | undefined;
  tracesSampleRateStr: string | undefined;
}) {
  if (!options.dsn) {
    return;
  }

  let rate = 0.0;
  if (options.tracesSampleRateStr) {
    const parsed = parseFloat(options.tracesSampleRateStr);
    if (!isNaN(parsed)) {
      rate = Math.max(0.0, Math.min(1.0, parsed));
    }
  }

  Sentry.init({
    dsn: options.dsn,
    environment: options.environment ?? "production",
    tracesSampleRate: rate,
    sendDefaultPii: false,
    beforeSend: sentryBeforeSend,
  });
}
