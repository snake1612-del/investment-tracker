import { describe, expect, it } from "vitest";
import { formatPercent, parseRatio } from "./exact-money";

describe("lossless rational display", () => {
  it.each([
    ["0", "1", "0%"],
    ["-1", "1", "−100%"],
    ["1", "20", "5%"],
    ["1", "3", "≈33.33333333%"],
  ])("formats %s/%s without Number", (numerator, denominator, expected) => {
    expect(formatPercent({ numerator, denominator })).toBe(expected);
  });
  it("arbitrary precision remains BigInt", () => {
    const numerator = "1" + "0".repeat(5000);
    const ratio = parseRatio({ numerator, denominator: "1" });
    expect(ratio.numerator).toBe(BigInt(numerator));
    expect(formatPercent({ numerator, denominator: "1" })).toBe(
      numerator + "00%",
    );
  });
});
