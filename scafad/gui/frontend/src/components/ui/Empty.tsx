import { ReactNode } from "react";
import { Card } from "./Card";

interface EmptyProps {
  title: string;
  body?: ReactNode;
  cta?: ReactNode;
}

export function Empty({ title, body, cta }: EmptyProps) {
  return (
    <Card>
      <div className="flex flex-col items-start gap-2 py-6">
        <div className="text-base font-semibold text-ink">{title}</div>
        {body && <div className="text-sm text-surface-muted">{body}</div>}
        {cta}
      </div>
    </Card>
  );
}
