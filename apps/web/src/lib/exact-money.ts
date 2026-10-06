export type MoneyWire = {
  currency_code: string;
  amount: { numerator: string; denominator: string };
};
export type ExactMoney = {
  currency: string;
  numerator: bigint;
  denominator: bigint;
};
const zero = BigInt(0);
const one = BigInt(1);
const scale = BigInt("100000000");

export function parseMoney(value: MoneyWire): ExactMoney {
  if (
    !value ||
    !/^[A-Z]{3}$/.test(value.currency_code) ||
    typeof value.amount?.numerator !== "string" ||
    typeof value.amount?.denominator !== "string" ||
    !/^(0|-?[1-9]\d*)$/.test(value.amount.numerator) ||
    !/^[1-9]\d*$/.test(value.amount.denominator)
  ) {
    throw new Error(
      "Invalid exact-money payload. No financial value has been substituted.",
    );
  }
  return { currency: value.currency_code, ...parseRatio(value.amount) };
}

export type RatioWire = { numerator: string; denominator: string };

export function parseRatio(value: RatioWire): {
  numerator: bigint;
  denominator: bigint;
} {
  if (
    !value ||
    typeof value.numerator !== "string" ||
    typeof value.denominator !== "string" ||
    !/^(0|-?[1-9]\d*)$/.test(value.numerator) ||
    !/^[1-9]\d*$/.test(value.denominator)
  )
    throw new Error(
      "Invalid exact-ratio payload. No financial value has been substituted.",
    );
  const numerator = BigInt(value.numerator);
  const denominator = BigInt(value.denominator);
  let a = numerator < zero ? -numerator : numerator;
  let b = denominator;
  while (b !== zero) [a, b] = [b, a % b];
  if (a !== one) throw new Error("Invalid non-canonical exact-money payload.");
  return { numerator, denominator };
}

export function formatPercent(value: RatioWire): string {
  const ratio = parseRatio(value);
  return formatMoney({
    currency: "%",
    numerator: ratio.numerator * BigInt(100),
    denominator: ratio.denominator,
  }).replace(" %", "%");
}

/** Half away from zero, presentation only. The original rational is never mutated. */
export function formatMoney(money: ExactMoney): string {
  const negative = money.numerator < zero;
  const magnitude = negative ? -money.numerator : money.numerator;
  const scaled = magnitude * scale;
  const remainder = scaled % money.denominator;
  let rounded = scaled / money.denominator;
  if (remainder * BigInt(2) >= money.denominator) rounded += one;
  const fraction = (rounded % scale)
    .toString()
    .padStart(8, "0")
    .replace(/0+$/, "");
  return `${remainder === zero ? "" : "≈"}${negative ? "−" : ""}${rounded / scale}${fraction ? `.${fraction}` : ""} ${money.currency}`;
}

export function normalizeDecimal(value: string): string {
  return value.trim().replace(",", ".");
}

export function decimalUnits(value: string, places = 12): bigint | null {
  const normalized = normalizeDecimal(value);
  const parts = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d{1,3}))?$/.exec(
    normalized,
  );
  if (!parts) return null;
  const fraction = parts[3] ?? "";
  const coefficient = BigInt(parts[2] + fraction);
  const shift =
    BigInt(places) - BigInt(fraction.length) + BigInt(parts[4] ?? "0");
  if (shift > BigInt(100) || shift < BigInt(-100)) return null;
  const divisor = shift < zero ? BigInt(10) ** -shift : one;
  if (coefficient % divisor !== zero) return null;
  const units =
    shift < zero ? coefficient / divisor : coefficient * BigInt(10) ** shift;
  return parts[1] ? -units : units;
}

export function positiveDecimalError(
  value: string,
  places = 8,
): string | undefined {
  const units = decimalUnits(value, places);
  if (units === null)
    return `Enter a decimal with at most ${places} significant decimal places.`;
  if (units <= zero) return "Must be greater than zero.";
  if (units >= BigInt(10) ** BigInt(16 + places))
    return "At most 16 integer digits are supported.";
}
