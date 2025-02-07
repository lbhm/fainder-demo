import { describe, it, expect } from "vitest";
import { useQueryParser } from "../composables/useQueryParser";

describe("Query Parser", () => {
  const { parseQuery } = useQueryParser();

  it("should parse empty query", () => {
    const result = parseQuery("");
    expect(result.terms).toEqual([]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse simple keyword query", () => {
    const result = parseQuery("KW(test)");
    expect(result.terms).toEqual([]);
    expect(result.remainingQuery).toBe("KW(test)");
  });

  it("should parse column name predicate", () => {
    const result = parseQuery("COLUMN(NAME(age;1))");
    expect(result.terms).toEqual([
      {
        type: "column",
        column: "age",
        threshold: 1,
      },
    ]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse percentile predicate", () => {
    const result = parseQuery("COLUMN(PERCENTILE(0.01;gt;1))");
    expect(result.terms).toEqual([
      {
        type: "percentile",
        percentile: 0.01,
        comparison: "gt",
        value: 1,
      },
    ]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse combined column predicate", () => {
    const result = parseQuery("COLUMN(NAME(age;1) AND PERCENTILE(0.01;gt;1))");
    expect(result.terms).toEqual([
      {
        type: "combined",
        column: "age",
        threshold: 1,
        percentile: 0.01,
        comparison: "gt",
        value: 1,
      },
    ]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse complex query with keyword and column predicate", () => {
    const result = parseQuery("KW(test) AND COLUMN(NAME(age;1))");
    expect(result.terms).toEqual([
      {
        type: "column",
        column: "age",
        threshold: 1,
      },
    ]);
    expect(result.remainingQuery).toBe("KW(test)");
  });

  it("should parse complex query with keyword and combined predicate", () => {
    const result = parseQuery(
      "KW(a) AND COLUMN(NAME(age;1) AND PERCENTILE(0.01;gt;1))",
    );
    expect(result.terms).toEqual([
      {
        type: "combined",
        column: "age",
        threshold: 1,
        percentile: 0.01,
        comparison: "gt",
        value: 1,
      },
    ]);
    expect(result.remainingQuery).toBe("KW(a)");
  });
});
