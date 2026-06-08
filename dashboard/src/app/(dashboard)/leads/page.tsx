"use client";
import { Users, Inbox } from "lucide-react";
import { useLeads } from "@/hooks/use-leads";
import { PageHeader } from "@/components/dashboard/page-header";
import { EmptyState } from "@/components/dashboard/empty-state";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate } from "@/lib/utils";

export default function LeadsPage() {
  const { data, backendPending } = useLeads();

  return (
    <>
      <PageHeader title="Leads"
        description="Contacts captured by your chatbots during conversations."
        action={backendPending ? <Badge variant="muted">API coming soon</Badge> : undefined} />

      {!data.length ? (
        <EmptyState icon={backendPending ? Inbox : Users}
          title={backendPending ? "Lead capture API not wired yet" : "No leads captured yet"}
          description={backendPending
            ? "The leads data model exists in the backend, but its API endpoints aren't built yet. Once /leads ships, captured contacts will appear here automatically."
            : "When visitors share contact details in a conversation, they'll show up here."} />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Phone</TableHead>
                <TableHead>Score</TableHead><TableHead>Status</TableHead><TableHead>Captured</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="font-medium">{l.name || "—"}</TableCell>
                  <TableCell>{l.email || "—"}</TableCell>
                  <TableCell>{l.phone || "—"}</TableCell>
                  <TableCell className="tabular-nums">{l.score}</TableCell>
                  <TableCell><StatusBadge status={l.status} /></TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(l.captured_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </>
  );
}
