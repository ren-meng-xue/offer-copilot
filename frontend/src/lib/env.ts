const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

export const env = {
  apiBaseUrl,
} as const;
