import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** Shared empty-state panel: icon in an amber-tinted ring, message, optional action. */
export function EmptyState({
  icon: Icon,
  children,
  action,
}: {
  icon: LucideIcon;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-border bg-card/40 p-12 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="size-6" />
      </span>
      <p className="max-w-sm text-sm text-muted-foreground">{children}</p>
      {action}
    </div>
  );
}
