"use client";
import { Building2, Check, ChevronsUpDown } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export function CompanySwitcher() {
  const { memberships, activeCompany, setActiveCompany } = useAuth();
  const current = memberships.find((m) => m.company_id === activeCompany);
  if (!memberships.length) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="h-9 w-full justify-between gap-2 px-2.5">
          <span className="flex min-w-0 items-center gap-2">
            <Building2 className="h-4 w-4 shrink-0 text-primary" />
            <span className="truncate text-sm font-medium">{current?.company_name ?? "Select workspace"}</span>
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-56">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Workspaces</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {memberships.map((m) => (
          <DropdownMenuItem key={m.company_id} onClick={() => setActiveCompany(m.company_id)}>
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <span className="flex-1 truncate">{m.company_name}</span>
            <span className="text-xs capitalize text-muted-foreground">{m.role_slug}</span>
            {m.company_id === activeCompany && <Check className="h-4 w-4 text-primary" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
