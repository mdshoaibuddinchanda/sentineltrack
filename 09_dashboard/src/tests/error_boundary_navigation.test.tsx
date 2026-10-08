import { afterEach, describe, it, expect, vi } from "vitest";
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "../components/layout/ErrorBoundary";

function FailingPage(): JSX.Element {
  throw new Error("camera data is unavailable");
}

function RouteHarness() {
  const location = useLocation();

  return (
    <>
      <Link to="/operations">Dashboard</Link>
      <ErrorBoundary key={location.pathname} fallbackTitle="Page Display Error">
        <Routes>
          <Route path="/broken" element={<FailingPage />} />
          <Route path="/operations" element={<div>Dashboard is ready</div>} />
        </Routes>
      </ErrorBoundary>
    </>
  );
}

describe("Page error recovery navigation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("opens the selected tab without requiring a retry after another page fails", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <MemoryRouter initialEntries={["/broken"]}>
        <RouteHarness />
      </MemoryRouter>
    );

    expect(screen.getByText("Page Display Error")).toBeDefined();

    fireEvent.click(screen.getByRole("link", { name: "Dashboard" }));

    expect(screen.getByText("Dashboard is ready")).toBeDefined();
  });
});
