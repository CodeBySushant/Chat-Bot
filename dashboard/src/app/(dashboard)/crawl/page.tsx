"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Globe, Play, Ban } from "lucide-react";
import { useCrawls, useStartCrawl, useCancelCrawl } from "@/hooks/use-crawls";
import { useAuth } from "@/providers/auth-provider";
import { PageHeader } from "@/components/dashboard/page-header";
import { EmptyState } from "@/components/dashboard/empty-state";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatDate } from "@/lib/utils";

export default function CrawlPage() {
  const { activeChatbot } = useAuth();
  const { data, isLoading } = useCrawls();
  const start = useStartCrawl();
  const cancel = useCancelCrawl();
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState("crawl");
  const [maxPages, setMaxPages] = useState(50);
  const [maxDepth, setMaxDepth] = useState(3);

  function onStart() {
    if (!url) return;
    start.mutate(
      { start_url: url, mode, max_pages: maxPages, max_depth: maxDepth },
      { onSuccess: () => { toast.success("Crawl started"); setUrl(""); },
        onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Failed to start") },
    );
  }

  if (!activeChatbot) {
    return (<><PageHeader title="Website Crawl" /><EmptyState icon={Globe} title="Select a chatbot first" /></>);
  }

  return (
    <>
      <PageHeader title="Website Crawl" description="Ingest web pages directly into the knowledge base." />
      <Card>
        <CardHeader><CardTitle>New crawl</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="url">Start URL</Label>
              <Input id="url" placeholder="https://docs.example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Mode</Label>
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="crawl">Crawl (follow links)</SelectItem>
                  <SelectItem value="sitemap">Sitemap</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="mp">Max pages</Label>
                <Input id="mp" type="number" min={1} max={500} value={maxPages} onChange={(e) => setMaxPages(+e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="md">Max depth</Label>
                <Input id="md" type="number" min={0} max={10} value={maxDepth} onChange={(e) => setMaxDepth(+e.target.value)} />
              </div>
            </div>
          </div>
          <Button onClick={onStart} disabled={start.isPending || !url}>
            <Play className="h-4 w-4" />{start.isPending ? "Starting…" : "Start crawl"}
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="font-display text-lg font-medium">Crawl jobs</h2>
        {isLoading ? (
          <Card className="p-6 text-sm text-muted-foreground">Loading…</Card>
        ) : !data?.length ? (
          <EmptyState icon={Globe} title="No crawls yet" description="Start a crawl above to pull in web content." />
        ) : (
          data.map((job) => {
            const total = job.pages_discovered || 0;
            const done = job.pages_processed + job.pages_failed;
            const pct = total ? Math.round((done / total) * 100) : job.status === "completed" ? 100 : 0;
            const live = job.status === "running" || job.status === "queued";
            return (
              <Card key={job.id} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{job.start_url}</p>
                    <p className="text-xs text-muted-foreground">{job.mode} · started {formatDate(job.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={job.status} />
                    {live && (
                      <Button variant="ghost" size="icon" className="text-destructive"
                        onClick={() => cancel.mutate(job.id, { onSuccess: () => toast.success("Cancelled") })} title="Cancel">
                        <Ban className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
                <div className="mt-3 space-y-1.5">
                  <Progress value={pct} />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{job.pages_processed} processed · {job.pages_failed} failed</span>
                    <span>{job.pages_discovered} discovered</span>
                  </div>
                </div>
                {job.error && <p className="mt-2 text-xs text-destructive">{job.error}</p>}
              </Card>
            );
          })
        )}
      </div>
    </>
  );
}
