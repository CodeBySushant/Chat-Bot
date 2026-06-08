"use client";
import { LogOut } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ChatbotSwitcher } from "./chatbot-switcher";

export function Topbar() {
  const { user, logout } = useAuth();
  const initials = (user?.full_name || user?.email || "?").slice(0, 2).toUpperCase();
  return (
    <header className="flex h-16 items-center justify-between gap-3 border-b bg-background/80 px-5 backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Active chatbot</span>
        <ChatbotSwitcher />
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="gap-2 px-2">
            <Avatar><AvatarFallback>{initials}</AvatarFallback></Avatar>
            <span className="hidden max-w-40 truncate text-sm md:block">{user?.email}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-52">
          <DropdownMenuLabel className="truncate">{user?.full_name || user?.email}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => logout()} className="text-destructive focus:text-destructive">
            <LogOut className="h-4 w-4" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
