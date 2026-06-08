"use client";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { MessagesSquare, Plus, Send, Sparkles, FileText } from "lucide-react";
import { useConversations, useCreateConversation, useMessages, streamPath } from "@/hooks/use-conversations";
import { useAuth } from "@/providers/auth-provider";
import { streamChat } from "@/lib/api/client";
import { PageHeader } from "@/components/dashboard/page-header";
import { EmptyState } from "@/components/dashboard/empty-state";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate } from "@/lib/utils";
import type { SourceRef } from "@/lib/api/types";

interface LiveMsg { role: string; content: string; sources?: SourceRef[]; pending?: boolean; }

export default function ConversationsPage() {
  const { activeCompany, activeChatbot } = useAuth();
  const { data: conversations } = useConversations();
  const createConv = useCreateConversation();
  const [activeConv, setActiveConv] = useState<string | null>(null);
  const { data: history } = useMessages(activeConv);
  const [live, setLive] = useState<LiveMsg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLive((history ?? []).map((m) => ({ role: m.role, content: m.content, sources: m.citations })));
  }, [history, activeConv]);

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [live, streaming]);

  async function send() {
    if (!input.trim() || !activeConv || !activeCompany || !activeChatbot) return;
    const question = input.trim();
    setInput("");
    setLive((p) => [...p, { role: "user", content: question }, { role: "assistant", content: "", pending: true }]);
    setStreaming(true);
    try {
      let acc = "";
      let sources: SourceRef[] = [];
      for await (const ev of streamChat(streamPath(activeCompany, activeChatbot, activeConv), { question })) {
        if (ev.type === "delta") { acc += ev.text as string; setLive((p) => { const n = [...p]; n[n.length - 1] = { role: "assistant", content: acc, pending: true }; return n; }); }
        else if (ev.type === "done") { sources = (ev.sources as SourceRef[]) ?? []; }
        else if (ev.type === "error") { toast.error(ev.message as string); }
      }
      setLive((p) => { const n = [...p]; n[n.length - 1] = { role: "assistant", content: acc || "(no response)", sources }; return n; });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Stream failed");
      setLive((p) => p.slice(0, -1));
    } finally {
      setStreaming(false);
    }
  }

  function newConversation() {
    createConv.mutate(undefined, { onSuccess: (c) => { setActiveConv(c.id); setLive([]); } });
  }

  if (!activeChatbot) {
    return (<><PageHeader title="Conversations" /><EmptyState icon={MessagesSquare} title="Select a chatbot first" /></>);
  }

  return (
    <>
      <PageHeader title="Conversations" description="Test your chatbot with grounded, streaming answers."
        action={<Button onClick={newConversation} disabled={createConv.isPending}><Plus className="h-4 w-4" />New chat</Button>} />

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <Card className="h-[calc(100vh-16rem)] overflow-y-auto p-2">
          {!conversations?.length ? (
            <p className="p-4 text-sm text-muted-foreground">No conversations yet.</p>
          ) : conversations.map((c) => (
            <button key={c.id} onClick={() => setActiveConv(c.id)}
              className={cn("flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-accent", activeConv === c.id && "bg-primary/10")}>
              <span className="font-medium">{c.title || "Untitled chat"}</span>
              <span className="text-xs text-muted-foreground">{c.message_count} msgs · {formatDate(c.started_at)}</span>
            </button>
          ))}
        </Card>

        <Card className="flex h-[calc(100vh-16rem)] flex-col">
          {!activeConv ? (
            <EmptyState className="m-auto border-0" icon={Sparkles} title="Pick or start a conversation" description="Create a new chat to ask your chatbot a question." />
          ) : (
            <>
              <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
                {live.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">Ask your first question below.</p>}
                {live.map((m, i) => (
                  <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                    <div className={cn("max-w-[80%] space-y-2 rounded-2xl px-4 py-2.5 text-sm", m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted")}>
                      <p className="whitespace-pre-wrap">{m.content}{m.pending && <span className="ml-0.5 animate-pulse">▍</span>}</p>
                      {m.sources && m.sources.length > 0 && (
                        <div className="flex flex-wrap gap-1 border-t border-border/50 pt-2">
                          {m.sources.map((s, j) => (
                            <Badge key={j} variant="muted" className="gap-1 text-[10px]">
                              <FileText className="h-3 w-3" />{s.title || "source"}{s.page_number ? ` p.${s.page_number}` : ""}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 border-t p-3">
                <Input placeholder="Ask a question…" value={input} onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !streaming && send()} disabled={streaming} />
                <Button onClick={send} disabled={streaming || !input.trim()}><Send className="h-4 w-4" /></Button>
              </div>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
