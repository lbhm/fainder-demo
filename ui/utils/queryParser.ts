export interface NameTerm {
  type: "name";
  column: string;
  threshold: number;
}

export interface PercentileTerm {
  type: "percentile";
  percentile: number;
  comparison: "gt" | "ge" | "lt" | "le";
  value: number;
}

export type Predicate = NameTerm | PercentileTerm;

export interface Term {
  predicates: Predicate[];
}

interface ParseResult {
  terms: Term[];
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

export function predicateToString(predicate: Predicate): string {
  if (predicate.type === "name") {
    return `NAME('${predicate.column}';${predicate.threshold})`;
  } else if (predicate.type === "percentile") {
    return `PERCENTILE(${predicate.percentile};${predicate.comparison};${predicate.value})`;
  }
  console.error(`Unknown predicate type: ${predicate}`);
  return "";
}

export function termToString(term: Term): string {
  const predicateStrings = term.predicates.map(predicateToString);
  return `COLUMN(${predicateStrings.join(" AND ")})`;
}

export function termsToString(terms: Term[]): string {
  return terms.map(termToString).join(" AND ");
}

export default function parseQuery(query: string): ParseResult {
  if (!query) return { terms: [], remainingQuery: "" };

  const normalizedQuery = query.trim();
  const remainingTerms: string[] = [];
  const terms: Term[] = [];
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
          const predicates: Predicate[] = [];

          // Handle predicates
          const parts = columnContent.split(/\s+AND\s+/);
          for (const part of parts) {
            const nameMatch = part.match(/NAME\(([^;]+);(\d+)\)/i);
            const percentileMatch = part.match(
              /PERCENTILE\((\d*\.?\d+);(ge|gt|le|lt);(\d*\.?\d+)\)/i,
            );

            if (nameMatch) {
              const [column, threshold] = nameMatch.slice(1);
              predicates.push({
                type: "name",
                column,
                threshold: parseFloat(threshold),
              });
            } else if (percentileMatch) {
              const [percentile, comparison, value] = percentileMatch.slice(1);
              predicates.push({
                type: "percentile",
                percentile: parseFloat(percentile),
                comparison: comparison as "gt" | "ge" | "lt" | "le",
                value: parseFloat(value),
              });
            }
          }

          if (predicates.length > 0) {
            terms.push({ predicates });
          }
          currentIndex = extracted.endIndex + 1;
          continue;
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
}
