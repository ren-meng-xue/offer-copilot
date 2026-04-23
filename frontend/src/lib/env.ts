const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!apiBaseUrl) {
  throw new Error("没有基础的请求地址 NEXT_PUBLIC_API_BASE_URL");
}

export const env = {
  apiBaseUrl,
} as const;
