/** Finance server state: accounts, categories, ledger, summary, settlements. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Schemas } from "@/lib/api";

export type Account = Schemas["AccountRead"];
export type Category = Schemas["CategoryRead"];
export type Transaction = Schemas["TransactionRead"];
export type TransactionCreate = Schemas["TransactionCreate"];
export type Settlement = Schemas["SettlementRead"];
export type SettlementCreate = Schemas["SettlementCreate"];
export type FinanceSummary = Schemas["FinanceSummary"];
export type OwedRow = Schemas["OwedRow"];

const KEY = ["finance"] as const;

async function unwrap<T>(promise: Promise<{ data?: T }>): Promise<T> {
  const { data } = await promise;
  if (data === undefined) throw new Error("Empty response");
  return data;
}

export function useAccounts() {
  return useQuery({ queryKey: [...KEY, "accounts"], queryFn: () => unwrap(api.GET("/api/accounts")) });
}

export function useCategories() {
  return useQuery({ queryKey: [...KEY, "categories"], queryFn: () => unwrap(api.GET("/api/categories")) });
}

export function useTransactions(month: string) {
  return useQuery({ queryKey: [...KEY, "transactions", month], queryFn: () => unwrap(api.GET("/api/transactions", { params: { query: { month, limit: 500 } } })) });
}

export function useFinanceSummary(month: string) {
  return useQuery({ queryKey: [...KEY, "summary", month], queryFn: () => unwrap(api.GET("/api/finance/summary", { params: { query: { month } } })) });
}

export function useSettlements(personId?: number) {
  return useQuery({
    queryKey: [...KEY, "settlements", personId ?? "all"],
    queryFn: () => unwrap(api.GET("/api/settlements", { params: { query: personId ? { person_id: personId } : {} } })),
  });
}

export function useFinanceMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: KEY });
    void qc.invalidateQueries({ queryKey: ["people"] });
    void qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const createTransaction = useMutation({ mutationFn: (body: TransactionCreate) => unwrap(api.POST("/api/transactions", { body })), onSettled: invalidate });
  const removeTransaction = useMutation({ mutationFn: (id: number) => api.DELETE("/api/transactions/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  const createSettlement = useMutation({ mutationFn: (body: SettlementCreate) => unwrap(api.POST("/api/settlements", { body })), onSettled: invalidate });
  const createCategory = useMutation({ mutationFn: (body: Schemas["CategoryCreate"]) => unwrap(api.POST("/api/categories", { body })), onSettled: invalidate });
  const createAccount = useMutation({ mutationFn: (body: Schemas["AccountCreate"]) => unwrap(api.POST("/api/accounts", { body })), onSettled: invalidate });
  return { createTransaction, removeTransaction, createSettlement, createCategory, createAccount };
}

export function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y ?? 2026, (m ?? 1) - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y ?? 2026, (m ?? 1) - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}
