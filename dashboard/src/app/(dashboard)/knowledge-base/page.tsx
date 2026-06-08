"use client";
import Link from "next/link";
import { Database, FileText, Globe, Layers, Search } from "lucide-react";
import { useDocuments, useSearch } from "@/hooks/use-documents";
import { useCrawls } from "@/hooks/use-crawls";
import { useAuth } from "@/providers/auth-provider";
import { PageHeader } from "@/components/dashboard/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { EmptyState } from "@/components/dashboard/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useState } from "react";

export default function KnowledgeBasePage() {
  const { activeChatbot } = useAuth();
  const docs = useDocuments();
  const crawls = useCrawls();
  const search = useSearch();
  const [q, setQ] = useState("");

  const ready = (docs.data ?? []).filter((d) => d.status === "ready").length;
  const chunks = (docs.data ?? []).reduce((s, d) => s + d.chunk_count, 0);
  const tokens = (docs.data ?? []).reduce((s, d) => s + d.token_count, 0);

  if (!activeChatbot) {
    return (
      <>
        <PageHeader title="Knowledge Base" />
        <EmptyState icon={Database} title="Select a chatbot" description="Choose or create a chatbot to manage its knowledge base." />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Knowledge Base" description="Everything your chatbot can reference when answering." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Documents" value={docs.data?.length ?? 0} hint={`${ready} ready`} icon={FileText} />
        <StatCard label="Chunks" value={chunks} icon={Layers} />
        <StatCard label="Tokens indexed" value={tokens.toLocaleString()} icon={Database} />
        <StatCard label="Crawl jobs" value={crawls.data?.length ?? 0} icon={Globe} />
      </div>

      <Card>
        <CardHeader><CardTitle>Semantic search</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input placeholder="Search the knowledge base…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && q && search.mutate(q)} />
            <Button onClick={() => q && search.mutate(q)} disabled={search.isPending}>
              <Search className="h-4 w-4" /> Search
            </Button>
          </div>
          {search.data && (
            <div className="space-y-2">
              {search.data.results.length === 0 && <p className="text-sm text-muted-foreground">No matches.</p>}
              {search.data.results.map((r, i) => (
                <div key={r.chunk_id ?? i} className="rounded-lg border p-3 text-sm">
                  <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                    <span>chunk #{r.chunk_index}</span>
                    <span>score {r.score.toFixed(3)}</span>
                  </div>
                  <p className="line-clamp-3 text-muted-foreground">{r.text}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><FileText className="h-4 w-4 text-primary" />Documents</CardTitle></CardHeader>
          <CardContent>
            <p className="mb-4 text-sm text-muted-foreground">Upload PDFs, Word, text, and more.</p>
            <Button asChild variant="outline" className="w-full"><Link href="/documents">Manage documents</Link></Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Globe className="h-4 w-4 text-primary" />Website Crawl</CardTitle></CardHeader>
          <CardContent>
            <p className="mb-4 text-sm text-muted-foreground">Ingest entire sites or sitemaps automatically.</p>
            <Button asChild variant="outline" className="w-full"><Link href="/crawl">Manage crawls</Link></Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
