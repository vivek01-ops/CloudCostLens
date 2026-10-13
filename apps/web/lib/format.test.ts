import { describe, expect, it } from "vitest";

import { formatMoney, formatPercent, valueOrEmDash } from "./format";

describe("formatMoney", () => {
  it("formats USD with two decimals", () => {
    expect(formatMoney(41.6)).toBe("$41.60");
  });

  it("accepts string amounts (as returned by the API)", () => {
    expect(formatMoney("1234.5")).toBe("$1,234.50");
  });
});

describe("formatPercent", () => {
  it("renders an em dash for missing telemetry rather than zero", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(undefined)).toBe("—");
  });

  it("formats a real value", () => {
    expect(formatPercent(3.24)).toBe("3.2%");
  });
});

describe("valueOrEmDash", () => {
  it("does not coerce missing values to zero", () => {
    expect(valueOrEmDash(null)).toBe("—");
    expect(valueOrEmDash(0)).toBe(0);
  });
});