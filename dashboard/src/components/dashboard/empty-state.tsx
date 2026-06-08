import { cn } from "@/lib/utils";

export function EmptyState({ icon: Icon, title, description, action, className }: {
  icon?: React.ComponentType<{ className?: string }>; title: string;
  description?: string; action?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center", className)}>
      {Icon && (
        <span className="mb-4 rounded-full bg-muted p-3 text-muted-foreground">
          <Icon className="h-6 w-6" />
        </span>
      )}
      <h3 className="font-display text-lg font-medium">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
