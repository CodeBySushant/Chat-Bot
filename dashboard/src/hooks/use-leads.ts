"use client";
import type { Lead } from "@/lib/api/types";
// Leads have a backend table but no API endpoints yet. This hook returns an empty
// dataset and flags the page so it can render an accurate "not yet available" state
// rather than fabricating data. Swap in a real query once /leads ships.
export function useLeads() {
  return { data: [] as Lead[], isLoading: false, backendPending: true };
}
