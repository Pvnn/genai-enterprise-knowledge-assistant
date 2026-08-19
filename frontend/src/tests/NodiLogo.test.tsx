/**
 * NodiLogo Component Tests.
 * Owner: P7
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import NodiLogo from "../chat/NodiLogo";

describe("NodiLogo", () => {
  it("renders the SVG with NODI logo aria label", () => {
    render(<NodiLogo size={32} className="test-class" />);
    const svgElement = screen.getByLabelText("NODI logo");
    expect(svgElement).toBeInTheDocument();
    expect(svgElement).toHaveAttribute("width", "32");
    expect(svgElement).toHaveAttribute("height", "32");
    expect(svgElement).toHaveClass("test-class");
  });

  it("renders the three connection lines and three nodes", () => {
    const { container } = render(<NodiLogo size={24} />);
    const lines = container.querySelectorAll("line");
    const circles = container.querySelectorAll("circle");

    expect(lines.length).toBe(3);
    expect(circles.length).toBeGreaterThanOrEqual(3);
  });
});
