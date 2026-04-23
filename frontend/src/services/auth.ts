import { post } from "@/lib/http";

export type LoginPayload = {
  email: string;
  password: string;
};

export type LoginResult = {
  access_token: string;
  token_type: string;
};

export type RegisterPayload = {
  email: string;
  username: string;
  current_identity?: string;
  password: string;
};

// 登录接口：
// POST /auth/login
export function login(payload: LoginPayload) {
  return post<LoginResult>("/auth/login", payload);
}

// 注册接口：
// POST /auth/register
export function register(payload: RegisterPayload) {
  return post<null>("/auth/register", payload);
}
