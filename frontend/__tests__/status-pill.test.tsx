import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusPill } from "@/components/ui/status-pill";

describe("StatusPill", () => {
  it("formats machine values for people and identifies missing classifications", () => {
    const { rerender } = render(<StatusPill value="waiting_on_approval" />);
    expect(screen.getByText("waiting on approval")).toBeInTheDocument();

    rerender(<StatusPill value={null} />);
    expect(screen.getByText("Unclassified")).toBeInTheDocument();
  });
});
