import { describe, it, expect } from "vitest";
import parseQuery from "../utils/queryParser";

describe("Query Parser", () => {
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
        predicates: [
          {
            type: "name",
            column: "age",
            threshold: 1,
          },
        ],
      },
    ]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse percentile predicate", () => {
    const result = parseQuery("COLUMN(PERCENTILE(0.01;gt;1))");
    expect(result.terms).toEqual([
      {
        predicates: [
          {
            type: "percentile",
            percentile: 0.01,
            comparison: "gt",
            value: 1,
          },
        ],
      },
    ]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse combined column predicate", () => {
    const result = parseQuery("COLUMN(NAME(age;1) AND PERCENTILE(0.01;gt;1))");
    expect(result.terms).toEqual([
      {
        predicates: [
          {
            type: "name",
            column: "age",
            threshold: 1,
          },
          {
            type: "percentile",
            percentile: 0.01,
            comparison: "gt",
            value: 1,
          },
        ],
      },
    ]);
    expect(result.remainingQuery).toBe("");
  });

  it("should parse complex query with keyword and column predicate", () => {
    const result = parseQuery("KW(test) AND COLUMN(NAME(age;1))");
    expect(result.terms).toEqual([
      {
        predicates: [
          {
            type: "name",
            column: "age",
            threshold: 1,
          },
        ],
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
        predicates: [
          {
            type: "name",
            column: "age",
            threshold: 1,
          },
          {
            type: "percentile",
            percentile: 0.01,
            comparison: "gt",
            value: 1,
          },
        ],
      },
    ]);
    expect(result.remainingQuery).toBe("KW(a)");
  });

  it("should parse complex query with keyword and multiple predicates with a different order", () => {
    const result = parseQuery(
      "COLUMN(NAME(age;1) AND PERCENTILE(0.01;gt;1)) AND KW(a)",
    );
    expect(result.terms).toEqual([
      {
        predicates: [
          {
            type: "name",
            column: "age",
            threshold: 1,
          },
          {
            type: "percentile",
            percentile: 0.01,
            comparison: "gt",
            value: 1,
          },
        ],
      },
    ]);
    expect(result.remainingQuery).toBe("KW(a)");
  });

  it("should parse complex query with multiple terms and keywords", () => {
    const result = parseQuery(
      "COLUMN(NAME(age;1) AND PERCENTILE(0.01;gt;1)) AND KW(a AND b) AND COLUMN(NAME(height;2)) AND KW(c)",
    );

    expect(result.terms).toEqual([
      {
        predicates: [
          {
            type: "name",
            column: "age",
            threshold: 1,
          },
          {
            type: "percentile",
            percentile: 0.01,
            comparison: "gt",
            value: 1,
          },
        ],
      },
      {
        predicates: [
          {
            type: "name",
            column: "height",
            threshold: 2,
          },
        ],
      },
    ]);
    expect(result.remainingQuery).toBe("KW(a AND b) AND KW(c)");
  });
});
