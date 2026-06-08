"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bot, CreditCard, FileText, Globe, LayoutDashboard, Library, MessagesSquare, Settings, UserCircle, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { CompanySwitcher } from "./company-switcher";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/knowledge-base", label: "Knowledge Base", icon: Library },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/crawl", label: "Website Crawl", icon: Globe },
  { href: "/chatbot", label: "Chatbot Settings", icon: Bot },
  { href: "/conversations", label: "Conversations", icon: MessagesSquare },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/account", label: "Account Settings", icon: UserCircle },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r bg-card/60 md:flex">
      <div className="flex h-16 items-center gap-2 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <MessagesSquare className="h-5 w-5" />
        </span>
        <span className="font-display text-lg font-semibold tracking-tight">Ember<span className="text-primary">Chat</span></span>
      </div>
      <div className="px-3 pb-3"><CompanySwitcher /></div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3">
        <Link href="/account" className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground hover:text-foreground">
          <Settings className="h-3.5 w-3.5" /> Manage workspace
        </Link>
      </div>
    </aside>
  );
}
