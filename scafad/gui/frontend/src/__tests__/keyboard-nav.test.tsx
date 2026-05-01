import { describe, expect, it, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { useState } from "react";

import { useTableKeyboardNav, isTypingTarget } from "@/lib/keyboard";

interface Row { id: string }

function Harness({
  rows,
  onOpenDetail,
  onToggleSelection,
  onAssignToMe,
}: {
  rows: Row[];
  onOpenDetail?: (r: Row) => void;
  onToggleSelection?: (r: Row) => void;
  onAssignToMe?: () => void;
}) {
  const [focused, setFocused] = useState(0);
  useTableKeyboardNav<Row>({
    rows,
    focusedIndex: focused,
    setFocusedIndex: setFocused,
    onOpenDetail,
    onToggleSelection,
    onAssignToMe,
  });
  return (
    <div data-testid="harness">
      <span data-testid="focused-id">{rows[focused]?.id ?? ""}</span>
      <input data-testid="text-input" />
    </div>
  );
}

describe("useTableKeyboardNav", () => {
  it("moves focus down on j", () => {
    const rows = [{ id: "a" }, { id: "b" }, { id: "c" }];
    const { getByTestId } = render(<Harness rows={rows} />);
    fireEvent.keyDown(window, { key: "j" });
    expect(getByTestId("focused-id").textContent).toBe("b");
  });

  it("moves focus up on k", () => {
    const rows = [{ id: "a" }, { id: "b" }];
    const { getByTestId } = render(<Harness rows={rows} />);
    fireEvent.keyDown(window, { key: "j" });
    fireEvent.keyDown(window, { key: "k" });
    expect(getByTestId("focused-id").textContent).toBe("a");
  });

  it("triggers onOpenDetail on Enter", () => {
    const onOpen = vi.fn();
    const rows = [{ id: "a" }];
    render(<Harness rows={rows} onOpenDetail={onOpen} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onOpen).toHaveBeenCalledWith({ id: "a" });
  });

  it("triggers onToggleSelection on Space", () => {
    const onToggle = vi.fn();
    const rows = [{ id: "a" }];
    render(<Harness rows={rows} onToggleSelection={onToggle} />);
    fireEvent.keyDown(window, { key: " " });
    expect(onToggle).toHaveBeenCalled();
  });

  it("triggers onAssignToMe on a", () => {
    const onAssign = vi.fn();
    render(<Harness rows={[{ id: "a" }]} onAssignToMe={onAssign} />);
    fireEvent.keyDown(window, { key: "a" });
    expect(onAssign).toHaveBeenCalled();
  });

  it("ignores key events when focus is in an input", () => {
    const onOpen = vi.fn();
    const { getByTestId } = render(
      <Harness rows={[{ id: "a" }, { id: "b" }]} onOpenDetail={onOpen} />
    );
    const input = getByTestId("text-input") as HTMLInputElement;
    input.focus();
    expect(isTypingTarget(input)).toBe(true);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onOpen).not.toHaveBeenCalled();
  });
});
