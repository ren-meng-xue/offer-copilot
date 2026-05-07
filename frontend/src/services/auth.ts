import { post } from "@/lib/http";

export type LoginPayload = {
  email: string;
  password: string;
};

export type LoginResult = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type RegisterPayload = {
  email: string;
  username: string;
  current_identity?: string;
  password: string;
};

export type ForgotPasswordPayload = {
  email: string;
};

export type ResetPasswordPayload = {
  token: string;
  new_password: string;
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

// 忘记密码接口：
// POST /auth/forgot-password
export function forgotPassword(payload: ForgotPasswordPayload) {
  return post<null>("/auth/forgot-password", payload);
}

// 重置密码接口：
// POST /auth/reset-password
export function resetPassword(payload: ResetPasswordPayload) {
  return post<null>("/auth/reset-password", payload);
}

// 退出登录接口：
// POST /auth/logout
export function logout() {
  return post<null>("/auth/logout", {}, { auth: true });
}
