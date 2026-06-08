"use client";
import Link from "next/link";
import { Bot, FileText, Globe, MessagesSquare, ArrowRight } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { useDocuments } from "@/hooks/use-documents";
import { useConversations } from "@/hooks/use-conversations";
import { useCrawls } from "@/hooks/use-crawls";
import { PageHeader } from "@/components/dashboard/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { user, chatbots, memberships, activeCompany } = useAuth();
  const docs = useDocuments();
  const convs = useConversations();
  const crawls = useCrawls();
  const company = memberships.find((m) => m.company_id === activeCompany);

  const ready = (docs.data ?? []).filter((d) => d.status === "ready").length;
  const totalMsgs = (convs.data ?? []).reduce((s, c) => s + c.message_count, 0);
  const pages = (crawls.data ?? []).reduce((s, c) => s + c.pages_processed, 0);

  return (
    <>
      <PageHeader
        title={`Welcome${user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}`}
        description={company ? `${company.company_name} · ${company.role_slug}` : "Your workspace overview"}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Chatbots" value={chatbots.length} icon={Bot} />
        <StatCard label="Ready documents" value={ready} hint={`${docs.data?.length ?? 0} total`} icon={FileText} />
        <StatCard label="Conversations" value={convs.data?.length ?? 0} hint={`${totalMsgs} messages`} icon={MessagesSquare} />
        <StatCard label="Crawled pages" value={pages} icon={Globe} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Get started</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {[
              { href: "/documents", label: "Upload documents", icon: FileText },
              { href: "/crawl", label: "Crawl a website", icon: Globe },
              { href: "/conversations", label: "Test your chatbot", icon: MessagesSquare },
            ].map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} className="flex items-center justify-between rounded-lg border p-3 text-sm transition-colors hover:bg-accent">
                <span className="flex items-center gap-3"><Icon className="h-4 w-4 text-primary" />{label}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </Link>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Your chatbots</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {chatbots.length === 0 && <p className="text-sm text-muted-foreground">No chatbots yet. Create one in Chatbot Settings.</p>}
            {chatbots.map((b) => (
              <div key={b.id} className="flex items-center justify-between rounded-lg border p-3">
                <span className="flex items-center gap-3 text-sm font-medium"><Bot className="h-4 w-4 text-primary" />{b.name}</span>
                <code className="text-xs text-muted-foreground">{b.slug}</code>
              </div>
            ))}
            <Button asChild variant="outline" className="w-full"><Link href="/chatbot">Manage chatbots</Link></Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
