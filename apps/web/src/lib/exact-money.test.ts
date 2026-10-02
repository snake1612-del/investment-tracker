import { describe, expect, it } from "vitest";
import {
  decimalUnits,
  formatMoney,
  parseMoney,
  positiveDecimalError,
} from "./exact-money";

describe("exact-money presentation", () => {
  it.each([
    ["25", "2", "12.5 USD"],
    ["100", "3", "≈33.33333333 USD"],
    ["0", "1", "0 USD"],
    ["-25", "2", "−12.5 USD"],
    ["1", "100000000", "0.00000001 USD"],
    ["1", "1000000000", "≈0 USD"],
    ["-1", "200000000", "≈−0.00000001 USD"],
    ["9007199254740993123456789", "1", "9007199254740993123456789 USD"],
  ])("formats %s/%s without Number", (numerator, denominator, display) => {
    const money = parseMoney({
      currency_code: "USD",
      amount: { numerator, denominator },
    });
    const original = { ...money };
    expect(typeof money.numerator).toBe("bigint");
    expect(formatMoney(money)).toBe(display);
    expect(money).toEqual(original);
  });
  it.each([
    ["1", "0"],
    ["1", "-2"],
    ["2", "4"],
    ["0", "2"],
    ["1e3", "1"],
    ["01", "1"],
  ])("rejects malformed %s/%s", (numerator, denominator) => {
    expect(() =>
      parseMoney({ currency_code: "USD", amount: { numerator, denominator } }),
    ).toThrow();
  });
  it("validates string decimals without losing huge integer precision", () => {
    expect(positiveDecimalError("9999999999999999,99999999")).toBeUndefined();
    expect(positiveDecimalError("1.2300000000")).toBeUndefined();
    expect(positiveDecimalError("10000000000000000")).toBeDefined();
    expect(positiveDecimalError("1.000000001")).toBeDefined();
    expect(positiveDecimalError("0")).toBeDefined();
    expect(positiveDecimalError("1E-12", 12)).toBeUndefined();
    expect(positiveDecimalError("1E-12", 8)).toBeDefined();
    expect(positiveDecimalError("1E-13", 12)).toBeDefined();
    expect(decimalUnits("-1E-12")).toBe(BigInt(-1));
    expect(decimalUnits("0E-12")).toBe(BigInt(0));
  });
});
