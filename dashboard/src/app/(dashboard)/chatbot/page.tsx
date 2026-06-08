"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Bot, Plus, Copy, Check, Code2 } from "lucide-react";
import { useChatbots, useCreateChatbot } from "@/hooks/use-chatbots";
import { useAuth } from "@/providers/auth-provider";
import { PageHeader } from "@/components/dashboard/page-header";
import { EmptyState } from "@/components/dashboard/empty-state";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button variant="ghost" size="icon" onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
      {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}

export default function ChatbotSettingsPage() {
  const { data } = useChatbots();
  const { activeChatbot, setActiveChatbot } = useAuth();
  const create = useCreateChatbot();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const current = (data ?? []).find((b) => b.id === activeChatbot) ?? data?.[0];
  const embed = current ? `<script src="https://cdn.emberchat.app/widget.js" data-key="${current.public_key}"></script>` : "";

  function onCreate() {
    create.mutate({ name, slug }, {
      onSuccess: (b) => { toast.success("Chatbot created"); setActiveChatbot(b.id); setOpen(false); setName(""); setSlug(""); },
      onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Failed"),
    });
  }

  return (
    <>
      <PageHeader title="Chatbot Settings" description="Manage your chatbots and deployment keys."
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button><Plus className="h-4 w-4" />New chatbot</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create chatbot</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="n">Name</Label>
                  <Input id="n" value={name} onChange={(e) => { setName(e.target.value); setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")); }} placeholder="Support Bot" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="s">Slug</Label>
                  <Input id="s" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="support-bot" />
                </div>
              </div>
              <DialogFooter><Button onClick={onCreate} disabled={create.isPending || !name || !slug}>Create</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      {!data?.length ? (
        <EmptyState icon={Bot} title="No chatbots yet" description="Create your first chatbot to start building." />
      ) : (
        <>
          {current && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2"><Bot className="h-5 w-5 text-primary" />{current.name}</CardTitle>
                  <StatusBadge status={current.status} />
                </div>
                <CardDescription>Slug: <code>{current.slug}</code></CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Public key</Label>
                  <div className="flex items-center gap-2 rounded-lg border bg-muted/40 p-2">
                    <code className="flex-1 truncate text-xs">{current.public_key}</code>
                    <CopyButton value={current.public_key} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="flex items-center gap-1.5"><Code2 className="h-3.5 w-3.5" />Embed snippet</Label>
                  <div className="flex items-center gap-2 rounded-lg border bg-muted/40 p-2">
                    <code className="flex-1 truncate text-xs">{embed}</code>
                    <CopyButton value={embed} />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Generation defaults (system prompt, temperature, retrieval depth, max tokens) are
                  managed server-side per chatbot. A settings-update endpoint is on the roadmap; this
                  panel will become editable once it ships.
                </p>
              </CardContent>
            </Card>
          )}

          <div className="space-y-3">
            <h2 className="font-display text-lg font-medium">All chatbots</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {data.map((b) => (
                <Card key={b.id} className={`cursor-pointer p-4 transition-colors hover:border-primary/40 ${b.id === current?.id ? "border-primary/50 bg-primary/5" : ""}`} onClick={() => setActiveChatbot(b.id)}>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 font-medium"><Bot className="h-4 w-4 text-primary" />{b.name}</span>
                    <StatusBadge status={b.status} />
                  </div>
                  <code className="mt-1 block text-xs text-muted-foreground">{b.slug}</code>
                </Card>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
