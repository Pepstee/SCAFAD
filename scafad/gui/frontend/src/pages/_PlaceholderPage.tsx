import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface PlaceholderProps {
  title: string;
  phase: string;
  description: string;
  bullets: string[];
}

export function PlaceholderPage({ title, phase, description, bullets }: PlaceholderProps) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        <Badge tone="info">{phase}</Badge>
      </div>
      <Card
        title="Coming in next phase"
        description={description}
      >
        <ul className="ml-4 list-disc space-y-1.5 text-sm text-ink">
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
        <div className="mt-5 rounded-md border border-surface-border bg-surface-subtle px-4 py-3 text-xs text-surface-muted">
          The shell, routing, and design system are already wired so the page
          can light up the moment its endpoints land. No infrastructure churn
          required for the upcoming phase.
        </div>
      </Card>
    </div>
  );
}
