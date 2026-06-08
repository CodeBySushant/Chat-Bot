"use client";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { FileText, Trash2, Upload, Eye, AlertCircle } from "lucide-react";
import { useDocuments, useUploadDocument, useDeleteDocument, useDocumentChunks } from "@/hooks/use-documents";
import { useAuth } from "@/providers/auth-provider";
import { PageHeader } from "@/components/dashboard/page-header";
import { EmptyState } from "@/components/dashboard/empty-state";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { formatBytes, formatDate } from "@/lib/utils";

export default function DocumentsPage() {
  const { activeChatbot } = useAuth();
  const { data, isLoading } = useDocuments();
  const upload = useUploadDocument();
  const del = useDeleteDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [viewing, setViewing] = useState<string | null>(null);
  const chunks = useDocumentChunks(viewing);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(file, {
      onSuccess: () => toast.success(`Uploaded ${file.name}`),
      onError: (err: unknown) => toast.error(err instanceof Error ? err.message : "Upload failed"),
    });
    if (fileRef.current) fileRef.current.value = "";
  }

  if (!activeChatbot) {
    return (<><PageHeader title="Documents" /><EmptyState icon={FileText} title="Select a chatbot first" /></>);
  }

  return (
    <>
      <PageHeader
        title="Documents"
        description="Upload source files to train this chatbot."
        action={
          <>
            <input ref={fileRef} type="file" className="hidden" onChange={onFile}
              accept=".pdf,.docx,.txt,.md,.csv" />
            <Button onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
              <Upload className="h-4 w-4" />{upload.isPending ? "Uploading…" : "Upload document"}
            </Button>
          </>
        }
      />

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
      ) : !data?.length ? (
        <EmptyState icon={FileText} title="No documents yet" description="Upload a PDF, Word doc, or text file to get started."
          action={<Button onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" />Upload document</Button>} />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead><TableHead>Type</TableHead><TableHead>Size</TableHead>
                <TableHead>Chunks</TableHead><TableHead>Status</TableHead><TableHead>Added</TableHead><TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="max-w-56 truncate font-medium">{d.title || "Untitled"}</TableCell>
                  <TableCell className="text-muted-foreground">{d.source_type}</TableCell>
                  <TableCell className="text-muted-foreground">{formatBytes(d.file_size)}</TableCell>
                  <TableCell className="tabular-nums">{d.chunk_count}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusBadge status={d.status} />
                      {d.status === "failed" && d.error && <span title={d.error}><AlertCircle className="h-3.5 w-3.5 text-destructive" /></span>}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(d.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => setViewing(d.id)} disabled={d.status !== "ready"} title="View chunks">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-destructive"
                        onClick={() => del.mutate(d.id, { onSuccess: () => toast.success("Deleted") })} title="Delete">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Document chunks</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] space-y-2 overflow-y-auto">
            {chunks.isLoading && <Skeleton className="h-24 w-full" />}
            {chunks.data?.map((c) => (
              <div key={c.id} className="rounded-lg border p-3 text-sm">
                <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>chunk #{c.chunk_index}{c.page_number ? ` · p.${c.page_number}` : ""}</span>
                  <span>{c.token_count} tokens</span>
                </div>
                <p className="whitespace-pre-wrap text-muted-foreground">{c.content}</p>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
