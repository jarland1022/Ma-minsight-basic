import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type MeInfo = {
  user_id: string | null;
  username: string | null;
  is_admin: boolean;
  via_api_key: boolean;
  role: string;
  is_readonly: boolean;
  expires_at: string | null;
  client_ip: string | null;
};

export function useMe() {
  return useQuery<MeInfo>({
    queryKey: ["auth-me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });
}
