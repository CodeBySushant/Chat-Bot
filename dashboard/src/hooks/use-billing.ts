"use client";
// Billing has a backend table but no API endpoints yet. Returns a known plan
// snapshot and flags the page as pending so nothing is fabricated.
export function useBilling() {
  return {
    plan: { name: "Starter", price: 0, interval: "month" as const },
    usage: null,
    isLoading: false,
    backendPending: true,
  };
}
