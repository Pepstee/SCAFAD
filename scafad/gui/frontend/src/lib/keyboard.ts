/**
 * Keyboard navigation utilities for the SCAFAD GUI.
 *
 * Phase 2 introduces row-level navigation in the Detection Inbox.
 * `useTableKeyboardNav` is a small custom hook that wires `j`/`k`/`space`/
 * `enter`/`c`/`a`/`e` to a table model.  All shortcuts are inert when focus
 * is inside an `input`, `textarea`, `select`, or `[contenteditable]` so the
 * filter bar never traps the typing user.
 */

import { useEffect } from "react";

export type KeyboardShortcut = "j" | "k" | "space" | "enter" | "c" | "a" | "e" | "escape";

export interface TableKeyboardNavOptions<T> {
  rows: T[];
  focusedIndex: number;
  setFocusedIndex: (idx: number) => void;
  onToggleSelection?: (row: T) => void;
  onOpenDetail?: (row: T) => void;
  onOpenCase?: (row: T) => void;
  onAssignToMe?: () => void;
  onEscalate?: () => void;
  enabled?: boolean;
}

/** Return true when the current document focus is inside a typing surface. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

/**
 * Wire the standard SCAFAD Inbox shortcut layout to a table.
 *
 * The hook is a pure DOM listener — it never re-renders unless one of the
 * memoised callbacks changes.  All callbacks are optional so embedding pages
 * can opt into a subset of the shortcuts.
 */
export function useTableKeyboardNav<T>(opts: TableKeyboardNavOptions<T>): void {
  const {
    rows,
    focusedIndex,
    setFocusedIndex,
    onToggleSelection,
    onOpenDetail,
    onOpenCase,
    onAssignToMe,
    onEscalate,
    enabled = true,
  } = opts;
  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined") return;
    const handler = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const max = rows.length - 1;
      const focused = Math.max(0, Math.min(focusedIndex, max));
      switch (event.key) {
        case "j":
        case "ArrowDown": {
          if (max < 0) return;
          event.preventDefault();
          setFocusedIndex(Math.min(max, focused + 1));
          return;
        }
        case "k":
        case "ArrowUp": {
          if (max < 0) return;
          event.preventDefault();
          setFocusedIndex(Math.max(0, focused - 1));
          return;
        }
        case " ":
        case "Spacebar": {
          if (max < 0 || !onToggleSelection) return;
          event.preventDefault();
          onToggleSelection(rows[focused]);
          return;
        }
        case "Enter": {
          if (max < 0 || !onOpenDetail) return;
          event.preventDefault();
          onOpenDetail(rows[focused]);
          return;
        }
        case "c": {
          if (max < 0 || !onOpenCase) return;
          event.preventDefault();
          onOpenCase(rows[focused]);
          return;
        }
        case "a": {
          if (!onAssignToMe) return;
          event.preventDefault();
          onAssignToMe();
          return;
        }
        case "e": {
          if (!onEscalate) return;
          event.preventDefault();
          onEscalate();
          return;
        }
        default:
          return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [
    enabled,
    rows,
    focusedIndex,
    setFocusedIndex,
    onToggleSelection,
    onOpenDetail,
    onOpenCase,
    onAssignToMe,
    onEscalate,
  ]);
}

/**
 * Map between Phase-2 shortcut keys and human-readable descriptions.
 * Used by the keyboard cheatsheet.
 */
export const KEYBOARD_HELP: Array<{ keys: string; description: string }> = [
  { keys: "j / ↓", description: "Move row focus down" },
  { keys: "k / ↑", description: "Move row focus up" },
  { keys: "Space", description: "Toggle row selection" },
  { keys: "Enter", description: "Open detection detail" },
  { keys: "c", description: "Open case drawer for focused row" },
  { keys: "a", description: "Assign selection to me" },
  { keys: "e", description: "Escalate currently open case" },
  { keys: "Esc", description: "Close drawer / dialog" },
  { keys: "?", description: "Show this cheatsheet" },
];
