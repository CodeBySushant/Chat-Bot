"use client";
import { BarChart3, FileText, Layers, MessagesSquare, Database, Globe } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAnalytics } from "@/hooks/use-analytics";
import { useAuth } from "@/providers/auth-provider";
import { PageHeader } from "@/components/dashboard/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { EmptyState } from "@/components/dashboard/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const STATUS_COLORS: Record<string, string> = {
  ready: "hsl(150 50% 36%)", processing: "hsl(18 80% 48%)", pending: "hsl(30 8% 60%)", failed: "hsl(0 72% 48%)",
};

export default function AnalyticsPage() {
  const { activeChatbot } = useAuth();
  const { stats, loading } = useAnalytics();

  if (!activeChatbot) {
    return (<><PageHeader title="Analytics" /><EmptyState icon={BarChart3} title="Select a chatbot first" /></>);
  }

  return (
    <>
      <PageHeader title="Analytics" description="A live snapshot of your knowledge base and chat activity."
        action={<Badge variant="muted">Derived from live data</Badge>} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Documents" value={loading ? "…" : stats.documents} hint={`${stats.readyDocuments} ready`} icon={FileText} />
        <StatCard label="Chunks indexed" value={loading ? "…" : stats.chunks} icon={Layers} />
        <StatCard label="Tokens" value={loading ? "…" : stats.tokens.toLocaleString()} icon={Database} />
        <StatCard label="Crawled pages" value={loading ? "…" : stats.crawledPages} icon={Globe} />
        <StatCard label="Conversations" value={loading ? "…" : stats.conversations} icon={MessagesSquare} />
        <StatCard label="Total messages" value={loading ? "…" : stats.messages} icon={MessagesSquare} />
      </div>

      <Card>
        <CardHeader><CardTitle>Documents by status</CardTitle></CardHeader>
        <CardContent>
          {stats.documents === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">No documents to chart yet.</p>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.byStatus} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
                  <XAxis dataKey="status" tickLine={false} axisLine={false} fontSize={12} stroke="hsl(var(--muted-foreground))" />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} stroke="hsl(var(--muted-foreground))" />
                  <Tooltip cursor={{ fill: "hsl(var(--muted))" }}
                    contentStyle={{ borderRadius: 8, border: "1px solid hsl(var(--border))", background: "hsl(var(--popover))", fontSize: 12 }} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {stats.byStatus.map((s) => <Cell key={s.status} fill={STATUS_COLORS[s.status] ?? "hsl(var(--primary))"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        These figures are computed client-side from live resources. Time-series analytics
        (daily active conversations, deflection rate, token spend over time) will appear here
        once the analytics rollup API is available.
      </p>
    </>
  );
}
