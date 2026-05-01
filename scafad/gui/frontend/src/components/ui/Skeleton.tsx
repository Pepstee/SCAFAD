import { clsx } from "@/lib/format";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden
      className={clsx("animate-pulse rounded-md bg-surface-subtle", className)}
    />
  );
}
