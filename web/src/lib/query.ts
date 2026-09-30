/** One server-state layer. Query keys live here so invalidation has one vocabulary. */

import { QueryClient } from "@tanstack/react-query";
import { isUnauthorized } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (failureCount, error) => !isUnauthorized(error) && failureCount < 2,
      refetchOnWindowFocus: true,
    },
  },
});

export const keys = {
  owner: ["owner"] as const,
  health: ["health"] as const,
  dashboard: ["dashboard"] as const,
  approvals: ["approvals"] as const,
  approval: (id: number) => ["approvals", id] as const,
  tasks: (filter?: string) => ["tasks", filter ?? "all"] as const,
  people: (filter?: string) => ["people", filter ?? "all"] as const,
  person: (id: number) => ["people", id] as const,
  companies: ["companies"] as const,
  applications: ["applications"] as const,
  application: (id: number) => ["applications", id] as const,
  postings: ["postings"] as const,
  log: (filter?: string) => ["log", filter ?? "all"] as const,
  memory: ["memory"] as const,
  chat: (threadId: string) => ["chat", threadId] as const,
  notifications: ["notifications", "badge"] as const,
  search: (q: string) => ["search", q] as const,
  projects: (filter?: string) => ["projects", filter ?? "all"] as const,
  learning: (filter?: string) => ["learning", filter ?? "all"] as const,
  courses: (filter?: string) => ["courses", filter ?? "all"] as const,
  assessments: (filter?: string) => ["assessments", filter ?? "all"] as const,
  fyp: (filter?: string) => ["fyp", filter ?? "all"] as const,
  documents: (filter?: string) => ["documents", filter ?? "all"] as const,
  email: ["email"] as const,
  emailThread: (id: string) => ["email", id] as const,
};
