import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isUnauthorized, type Schemas } from "./api";
import { keys } from "./query";

export type Owner = Schemas["Owner"];

/** `data === null` means "not signed in"; `undefined` means still loading. */
export function useOwner() {
  return useQuery({
    queryKey: keys.owner,
    queryFn: async (): Promise<Owner | null> => {
      try {
        const { data } = await api.GET("/api/auth/me");
        return data ?? null;
      } catch (error) {
        if (isUnauthorized(error)) return null;
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (password: string) => {
      const { data } = await api.POST("/api/auth/login", { body: { password } });
      return data ?? null;
    },
    onSuccess: (owner) => {
      qc.setQueryData(keys.owner, owner);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/auth/logout");
    },
    onSuccess: () => {
      qc.clear();
      qc.setQueryData(keys.owner, null);
    },
  });
}
