import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Home", () => {
  it("renders the Investment Tracker scaffold", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: "Investment Tracker" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Personal Investment Analytics Platform"),
    ).toBeInTheDocument();
  });
});
