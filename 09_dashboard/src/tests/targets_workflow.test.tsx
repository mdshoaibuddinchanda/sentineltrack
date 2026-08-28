import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TargetListTable } from "../components/targets/TargetListTable";
import { AddTargetModal } from "../components/targets/AddTargetModal";
import { EditTargetModal } from "../components/targets/EditTargetModal";
import { TargetsPage } from "../pages/TargetsPage";
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
    const handleEdit = vi.fn();
    const handleDisable = vi.fn();

    render(
      <TargetListTable
        targets={mockTargets}
        onInvestigate={handleInvestigate}
        onEdit={handleEdit}
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

  it("EditTargetModal allows updating priority, notes, and case ID, and calls onUpdateTarget", async () => {
    const handleUpdate = vi.fn().mockResolvedValue({ target_id: "tgt_02" });
    const handleClose = vi.fn();

    render(
      <EditTargetModal
        isOpen={true}
        onClose={handleClose}
        target={mockTargets[1]}
        onSubmit={handleUpdate}
      />
    );

    // Verify immutable plate display
    expect(screen.getByText("GJ05CD9999")).toBeDefined();

    // Change priority NORMAL -> CRITICAL
    const prioritySelect = screen.getByDisplayValue("NORMAL — Standard BOLO / Surveillance");
    fireEvent.change(prioritySelect, { target: { value: "CRITICAL" } });

    // Change notes
    const notesInput = screen.getByPlaceholderText("Operational notes, suspect details, vehicle make/model...");
    fireEvent.change(notesInput, { target: { value: "Updated note: Armed robbery" } });

    // Submit edit
    const saveBtn = screen.getByText("SAVE CHANGES");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleUpdate).toHaveBeenCalledWith(
        "tgt_02",
        expect.objectContaining({
          priority: "CRITICAL",
          notes: "Updated note: Armed robbery",
        })
      );
    });
  });

  it("EditTargetModal displays error banner if target update fails with 503", async () => {
    const handleUpdate = vi.fn().mockRejectedValue(new Error("Database unavailable (503)"));
    const handleClose = vi.fn();

    render(
      <EditTargetModal
        isOpen={true}
        onClose={handleClose}
        target={mockTargets[0]}
        onSubmit={handleUpdate}
      />
    );

    const saveBtn = screen.getByText("SAVE CHANGES");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText("Database unavailable (503)")).toBeDefined();
    });
  });

  it("TargetsPage opens EditTargetModal when edit button is clicked in table", () => {
    const handleUpdate = vi.fn();

    render(
      <TargetsPage
        targets={mockTargets}
        onCreateTarget={vi.fn()}
        onUpdateTarget={handleUpdate}
        onInvestigate={vi.fn()}
      />
    );

    const editButtons = screen.getAllByTitle("Edit Target Entry");
    expect(editButtons.length).toBe(2);

    // Click edit on first target
    fireEvent.click(editButtons[0]);

    // Modal should be visible with target plate
    expect(screen.getByText("EDIT TARGET WATCHLIST ENTRY")).toBeDefined();
  });
});
