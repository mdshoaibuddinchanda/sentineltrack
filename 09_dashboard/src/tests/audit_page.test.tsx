import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AuditPage } from "../pages/AuditPage";
import * as auditApi from "../api/audit";

vi.mock("../api/audit", () => ({
  listAuditEvents: vi.fn(),
}));

const MOCK_AUDIT_DATA: auditApi.AuditListResponse = {
  total: 2,
  items: [
    {
      audit_id: "aud-001-xyz",
      event_time_utc: "2026-08-28T12:00:00Z",
      actor_user_id: "usr-admin",
      actor_username: "admin_chief",
      actor_role: "ADMIN",
      action: "USER_CREATED",
      resource_type: "user",
      resource_id: "usr-op1",
      outcome: "SUCCESS",
      source_ip: "127.0.0.1",
      request_id: "req-12345",
      user_agent: "Mozilla/5.0",
      details: { username: "operator_ahmedabad", role: "OPERATOR" },
    },
    {
      audit_id: "aud-002-xyz",
      event_time_utc: "2026-08-28T12:05:00Z",
      actor_user_id: "usr-op1",
      actor_username: "operator_ahmedabad",
      actor_role: "OPERATOR",
      action: "ACK_ALERT",
      resource_type: "alert",
      resource_id: "alt-999",
      outcome: "SUCCESS",
      source_ip: "127.0.0.1",
      request_id: "req-67890",
      user_agent: "Mozilla/5.0",
      details: { acknowledged_by: "operator_ahmedabad" },
    },
  ],
};

describe("AuditPage Frontend Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders audit log table with correct backend schema fields", async () => {
    vi.mocked(auditApi.listAuditEvents).mockResolvedValue(MOCK_AUDIT_DATA);

    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText(/security audit trail/i)).toBeDefined();
      expect(screen.getByText("admin_chief")).toBeDefined();
      expect(screen.getByText("operator_ahmedabad")).toBeDefined();
      expect(screen.getAllByText("SUCCESS").length).toBeGreaterThan(0);
    });
  });

  it("opens audit event detail modal displaying audit_id and event_time_utc", async () => {
    vi.mocked(auditApi.listAuditEvents).mockResolvedValue(MOCK_AUDIT_DATA);

    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getAllByText("View")).toHaveLength(2);
    });

    fireEvent.click(screen.getAllByText("View")[0]);

    await waitFor(() => {
      expect(screen.getByText("AUDIT EVENT: aud-001-xyz")).toBeDefined();
      expect(screen.getByText("Timestamp (UTC):")).toBeDefined();
    });
  });
});
