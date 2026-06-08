import { Badge } from "@/components/ui/badge";

const MAP: Record<string, "default" | "success" | "destructive" | "muted" | "secondary"> = {
  ready: "success", completed: "success", active: "success", converted: "success",
  processing: "default", running: "default", pending: "muted", queued: "muted",
  open: "default", failed: "destructive", cancelled: "muted", lost: "destructive",
  closed: "muted", new: "secondary",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={MAP[status] ?? "secondary"} className="capitalize">{status}</Badge>;
}
