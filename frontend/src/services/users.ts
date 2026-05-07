import { get } from "@/lib/http";

export type CurrentUser = {
  id: number;
  username: string;
  email: string;
  status: string;
  current_identity?: string | null;
};

// 当前用户信息接口：
// GET /users
export function getCurrentUser() {
  return get<CurrentUser>("/users", { auth: true });
}
