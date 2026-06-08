"use client";
import { LogOut, ShieldCheck, Building2 } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { useMembers } from "@/hooks/use-members";
import { PageHeader } from "@/components/dashboard/page-header";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";

export default function AccountPage() {
  const { user, memberships, activeCompany, permissions, logout } = useAuth();
  const { data: members } = useMembers();
  const company = memberships.find((m) => m.company_id === activeCompany);
  const initials = (user?.full_name || user?.email || "?").slice(0, 2).toUpperCase();

  return (
    <>
      <PageHeader title="Account Settings" description="Your profile, workspace, and team." />

      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14"><AvatarFallback className="text-lg">{initials}</AvatarFallback></Avatar>
            <div>
              <p className="font-medium">{user?.full_name || "—"}</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
              {user?.email_verified_at ? <Badge variant="success" className="mt-1 gap-1"><ShieldCheck className="h-3 w-3" />Verified</Badge> : <Badge variant="muted" className="mt-1">Unverified</Badge>}
            </div>
          </div>
          <Separator />
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label>Full name</Label><Input defaultValue={user?.full_name ?? ""} disabled /></div>
            <div className="space-y-2"><Label>Email</Label><Input defaultValue={user?.email ?? ""} disabled /></div>
          </div>
          <p className="text-xs text-muted-foreground">Profile editing endpoints are on the roadmap; fields are read-only for now.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-4 w-4 text-primary" />Workspace</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{company?.company_name}</p>
              <p className="text-sm text-muted-foreground">Your role: <span className="capitalize">{company?.role_slug}</span></p>
            </div>
            {company && <StatusBadge status={company.status} />}
          </div>
          <div className="flex flex-wrap gap-1">
            {permissions.map((p) => <Badge key={p} variant="muted" className="text-[10px]">{p}</Badge>)}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Team members</CardTitle></CardHeader>
        <CardContent>
          {!members?.length ? (
            <p className="text-sm text-muted-foreground">No members found.</p>
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>Member</TableHead><TableHead>Role</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      <div className="font-medium">{m.full_name || "—"}</div>
                      <div className="text-xs text-muted-foreground">{m.email}</div>
                    </TableCell>
                    <TableCell className="capitalize">{m.role_slug}</TableCell>
                    <TableCell><StatusBadge status={m.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex items-center justify-between py-4">
          <div><p className="font-medium">Sign out</p><p className="text-sm text-muted-foreground">End your session on this device.</p></div>
          <Button variant="outline" onClick={() => logout()} className="text-destructive"><LogOut className="h-4 w-4" />Sign out</Button>
        </CardContent>
      </Card>
    </>
  );
}
