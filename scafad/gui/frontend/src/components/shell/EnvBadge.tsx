import { Badge } from "@/components/ui/Badge";

interface EnvBadgeProps {
  env: string;
}

export function EnvBadge({ env }: EnvBadgeProps) {
  const e = env.toLowerCase();
  const tone =
    e === "prod" || e === "production"
      ? "danger"
      : e === "staging" || e === "stage"
        ? "warn"
        : "info";
  return <Badge tone={tone}>{env}</Badge>;
}
