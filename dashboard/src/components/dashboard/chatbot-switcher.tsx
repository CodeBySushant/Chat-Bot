"use client";
import { Bot, Check, ChevronsUpDown } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export function ChatbotSwitcher() {
  const { chatbots, activeChatbot, setActiveChatbot } = useAuth();
  const current = chatbots.find((b) => b.id === activeChatbot);
  if (!chatbots.length) return <span className="text-sm text-muted-foreground">No chatbots yet</span>;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-2.5">
          <Bot className="h-4 w-4 text-primary" />
          <span className="max-w-40 truncate text-sm font-medium">{current?.name ?? "Select chatbot"}</span>
          <ChevronsUpDown className="h-4 w-4 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-52">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Chatbots</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {chatbots.map((b) => (
          <DropdownMenuItem key={b.id} onClick={() => setActiveChatbot(b.id)}>
            <Bot className="h-4 w-4 text-muted-foreground" />
            <span className="flex-1 truncate">{b.name}</span>
            {b.id === activeChatbot && <Check className="h-4 w-4 text-primary" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
