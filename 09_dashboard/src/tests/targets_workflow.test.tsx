import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TargetListTable } from "../components/targets/TargetListTable";
import { AddTargetModal } from "../components/targets/AddTargetModal";
import { Target } from "../types/api";

describe("Target Watchlist Workflow Tests", () => {
  const mockTargets: Target[] = [
    {
      target_id: "tgt_01",
      registration: "GJ01AB1234",
      normalized_registration: "GJ01AB1234",
      priority: "CRITICAL",
      enabled: true,
      created_at: "2026-08-28T10:00:00Z",
      notes: "Robbery suspect",
      metadata: { case_id: "FIR-101" },
    },
    {
      target_id: "tgt_02",
      registration: "GJ05CD9999",
      normalized_registration: "GJ05CD9999",
      priority: "NORMAL",
      enabled: false,
      created_at: "2026-08-28T09:00:00Z",
      notes: "Deactivated plate",
    },
  ];

  it("renders target list with plate, normalization, priority, and actions", () => {
    const handleInvestigate = vi.fn();
    const handleDisable = vi.fn();

    render(
      <TargetListTable
        targets={mockTargets}
        onInvestigate={handleInvestigate}
        onDisable={handleDisable}
      />
    );

    expect(screen.getAllByText("GJ01AB1234").length).toBeGreaterThan(0);
    expect(screen.getByText("CRITICAL")).toBeDefined();
    expect(screen.getByText("ACTIVE")).toBeDefined();
    expect(screen.getByText("DISABLED")).toBeDefined();
    expect(screen.getByText("Robbery suspect")).toBeDefined();
  });

  it("normalizes license plate preview in AddTargetModal and handles submission", async () => {
    const handleSubmit = vi.fn().mockResolvedValue({ target_id: "tgt_new" });
    const handleClose = vi.fn();

    render(
      <AddTargetModal
        isOpen={true}
        onClose={handleClose}
        onSubmit={handleSubmit}
      />
    );

    const plateInput = screen.getByPlaceholderText("e.g. GJ 01 AB 1234");
    fireEvent.change(plateInput, { target: { value: "gj 01 ab 5555" } });

    // Verify plate normalization preview
    expect(screen.getByText("GJ01AB5555")).toBeDefined();

    const submitBtn = screen.getByText("REGISTER TARGET");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          registration: "GJ01AB5555",
          priority: "CRITICAL",
        })
      );
    });
  });

  it("displays error message if target creation fails with 503 or 409 conflict", async () => {
    const handleSubmit = vi.fn().mockRejectedValue(new Error("Database unavailable (503)"));
    const handleClose = vi.fn();

    render(
      <AddTargetModal
        isOpen={true}
        onClose={handleClose}
        onSubmit={handleSubmit}
      />
    );

    const plateInput = screen.getByPlaceholderText("e.g. GJ 01 AB 1234");
    fireEvent.change(plateInput, { target: { value: "GJ01AB1234" } });

    const submitBtn = screen.getByText("REGISTER TARGET");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Database unavailable (503)")).toBeDefined();
    });
  });
});
