interface BaseSearchTerm {
  type: "column" | "percentile" | "combined";
}

interface ColumnTerm extends BaseSearchTerm {
  type: "column";
  column: string;
  threshold: number;
}

interface PercentileTerm extends BaseSearchTerm {
  type: "percentile";
  percentile: number;
  comparison: "gt" | "ge" | "lt" | "le";
  value: number;
}

interface CombinedTerm extends BaseSearchTerm {
  type: "combined";
  column: string;
  threshold: number;
  percentile: number;
  comparison: "gt" | "ge" | "lt" | "le";
  value: number;
}

export type SearchTerm = ColumnTerm | PercentileTerm | CombinedTerm;

interface ParseResult {
  terms: SearchTerm[];
  remainingQuery: string;
}

function extractBalancedParentheses(
  str: string,
  startIndex: number,
): { content: string; endIndex: number } | null {
  let count = 1;
  let i = startIndex;

  while (i < str.length && count > 0) {
    i++;
    if (str[i] === "(") count++;
    if (str[i] === ")") count--;
  }

  if (count === 0) {
    return {
      content: str.substring(startIndex + 1, i),
      endIndex: i,
    };
  }
  return null;
}

export function useQueryParser() {
  const parseQuery = (query: string): ParseResult => {
    if (!query) return { terms: [], remainingQuery: "" };

    const normalizedQuery = query.trim();
    const remainingTerms: string[] = [];
    const terms: SearchTerm[] = [];
    let currentIndex = 0;

    while (currentIndex < normalizedQuery.length) {
      // Skip whitespace
      while (
        currentIndex < normalizedQuery.length &&
        normalizedQuery[currentIndex].trim() === ""
      ) {
        currentIndex++;
      }

      // Check for AND operator
      if (
        currentIndex + 3 < normalizedQuery.length &&
        normalizedQuery
          .substring(currentIndex, currentIndex + 3)
          .toUpperCase() === "AND"
      ) {
        currentIndex += 3;
        continue;
      }

      // Look for COLUMN expressions
      if (
        currentIndex + 6 < normalizedQuery.length &&
        normalizedQuery
          .substring(currentIndex, currentIndex + 6)
          .toUpperCase() === "COLUMN"
      ) {
        const startParen = normalizedQuery.indexOf("(", currentIndex);
        if (startParen !== -1) {
          const extracted = extractBalancedParentheses(
            normalizedQuery,
            startParen,
          );
          if (extracted) {
            const columnContent = extracted.content;

            if (columnContent.includes(" AND ")) {
              // Handle combined predicate
              const [namePart, percentilePart] =
                columnContent.split(/\s+AND\s+/);
              const nameMatch = namePart.match(/NAME\(([^;]+);(\d+)\)/i);
              const percentileMatch = percentilePart?.match(
                /PERCENTILE\((\d*\.?\d+);(ge|gt|le|lt);(\d*\.?\d+)\)/i,
              );

              if (nameMatch && percentileMatch) {
                const [column, threshold] = nameMatch.slice(1);
                const [percentile, comparison, value] =
                  percentileMatch.slice(1);

                terms.push({
                  type: "combined",
                  column,
                  threshold: parseFloat(threshold),
                  percentile: parseFloat(percentile),
                  comparison: comparison as "gt" | "ge" | "lt" | "le",
                  value: parseFloat(value),
                });
                currentIndex = extracted.endIndex + 1;
                continue;
              }
            } else if (columnContent.startsWith("NAME")) {
              // Handle column name predicate
              const nameMatch = columnContent.match(/NAME\(([^;]+);(\d+)\)/i);
              if (nameMatch) {
                const [column, threshold] = nameMatch.slice(1);
                terms.push({
                  type: "column",
                  column,
                  threshold: parseFloat(threshold),
                });
                currentIndex = extracted.endIndex + 1;
                continue;
              }
            } else if (columnContent.startsWith("PERCENTILE")) {
              // Handle percentile predicate
              const percentileMatch = columnContent.match(
                /PERCENTILE\((\d*\.?\d+);(ge|gt|le|lt);(\d*\.?\d+)\)/i,
              );
              if (percentileMatch) {
                const [percentile, comparison, value] =
                  percentileMatch.slice(1);
                terms.push({
                  type: "percentile",
                  percentile: parseFloat(percentile),
                  comparison: comparison as "gt" | "ge" | "lt" | "le",
                  value: parseFloat(value),
                });
                currentIndex = extracted.endIndex + 1;
                continue;
              }
            }
          }
        }
      }

      // If we reach here, treat it as a remaining term
      let termEnd = normalizedQuery.indexOf(" AND ", currentIndex);
      if (termEnd === -1) termEnd = normalizedQuery.length;
      const term = normalizedQuery.substring(currentIndex, termEnd).trim();
      if (term) remainingTerms.push(term);
      currentIndex = termEnd + 5; // Skip past " AND "
    }

    return {
      terms,
      remainingQuery: remainingTerms.join(" AND ").trim(),
    };
  };

  return {
    parseQuery,
  };
}
