import { env } from "@/lib/env";

type RequestMethod = "GET" | "POST";
type RequestBody = Record<string, unknown>;

type RequestOptions = {
  // 当前阶段只需要 GET / POST，后面有新接口再继续扩。
  method?: RequestMethod;
  body?: RequestBody;
  headers?: HeadersInit;
  // 受保护接口会在这里传 Bearer Token。
  token?: string;
  signal?: AbortSignal;
};

type ApiEnvelope<T> = {
  code: number;
  msg: string;
  data: T;
};

// 后端返回非 2xx 时，统一抛这个错误给页面或服务层处理。
export class ApiError extends Error {
  status: number;
  code: number;
  data: unknown;

  constructor({
    message,
    status,
    code,
    data,
  }: {
    message: string;
    status: number;
    code: number;
    data?: unknown;
  }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.data = data ?? null;
  }
}

// 通用请求入口：
// 1. 拼接基础地址
// 2. 自动处理 JSON body
// 3. 自动挂 token
// 4. 按后端统一响应结构解析 { code, msg, data }
export async function request<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const { method = "GET", body, headers, token, signal } = options;
  const requestHeaders = new Headers(headers);

  if (!requestHeaders.has("Content-Type") && body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  const payload = (await parseJson<ApiEnvelope<TResponse>>(response)) ?? null;

  if (!response.ok) {
    throw new ApiError({
      message: payload?.msg ?? "请求失败，请稍后重试",
      status: response.status,
      code: payload?.code ?? response.status,
      data: payload?.data,
    });
  }

  if (!payload) {
    throw new ApiError({
      message: "接口返回为空",
      status: response.status,
      code: response.status,
    });
  }

  return payload.data;
}

// 查询类接口统一走 get。
export function get<TResponse>(
  path: string,
  options: Omit<RequestOptions, "method" | "body"> = {},
) {
  return request<TResponse>(path, {
    ...options,
    method: "GET",
  });
}

// 创建 / 登录 / 注册这类提交统一走 post。
export function post<TResponse>(
  path: string,
  body: RequestBody,
  options: Omit<RequestOptions, "method" | "body"> = {},
) {
  return request<TResponse>(path, {
    ...options,
    method: "POST",
    body,
  });
}

function buildUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  return `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseJson<T>(response: Response): Promise<T | null> {
  // 不是 JSON 响应时，当前先按 null 处理，避免直接解析报错。
  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json() as Promise<T>;
}
