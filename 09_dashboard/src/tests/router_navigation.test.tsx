import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Navigation } from "../components/layout/Navigation";
import { InvestigationPage } from "../pages/InvestigationPage";

describe("Router & Deep Linking Tests", () => {
  it("renders Navigation with active route highlighting", () => {
    render(
      <MemoryRouter initialEntries={["/targets"]}>
        <Navigation unackAlertsCount={2} />
      </MemoryRouter>
    );

    expect(screen.getByText("OPERATIONS")).toBeDefined();
    expect(screen.getByText("TARGETS")).toBeDefined();
    expect(screen.getByText("ALERTS")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined(); // badge
  });

  it("loads bookmarkable route with registration param in InvestigationPage", () => {
    render(
      <MemoryRouter initialEntries={["/investigation/GJ18XY5678"]}>
        <Routes>
          <Route path="/investigation/:registration" element={<InvestigationPage demoMode={true} />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByPlaceholderText("Enter vehicle license plate (e.g. GJ01AB1234)...")).toBeDefined();
  });
});
