import json
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_COLUMN_NAMES,
    DEFAULT_HIGH_PERCENTILE,
    DEFAULT_INDICES,
    DEFAULT_KEYWORDS,
    DEFAULT_LARGE_THRESHOLDS,
    DEFAULT_OPERATORS,
    DEFAULT_SMALL_PERCENTILE,
    DEFAULT_SMALL_THRESHOLDS,
    LOGICAL_OPERATORS,
    MAX_COMBINED_TERMS,
    MEDICAL_KEYWORDS,
    N_WAY_TEST_COMBINATIONS,
    TEST_COLUMN_NAMES,
    TEST_COMBINATIONS,
    TEST_INDICES,
    TEST_LARGE_THRESHOLDS,
    TEST_OPERATORS,
    TEST_SMALL_THRESHOLDS,
)


def generate_base_keyword_queries() -> dict[str, dict[str, Any]]:
    return {
        "double_wildcard_search": {"query": "kw(*a*)"},
        "wildcard_search": {"query": "kw(a*)"},
    }


def generate_simple_keyword_queries(
    keywords: list[str] | None = None,
    prefix: str = "simple_keyword",
    field_name: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Generate simple keyword queries.

    Args:
        keywords: List of keywords to search for. If None, uses default list
        prefix: Prefix for the query names
        field_name: Optional field name for field-specific searches
    """
    if keywords is None:
        keywords = DEFAULT_KEYWORDS

    field_prefix = f"{field_name}:" if field_name else ""
    return {
        f"{prefix}_{i + 1}": {"query": f"kw({field_prefix}{word})"}
        for i, word in enumerate(keywords)
    }


def generate_complex_keyword_queries(base_word: str) -> dict[str, dict[str, Any]]:
    return {
        "simple_keyword": {"query": f"kw({base_word})"},
        "not_keyword": {"query": f"NOT kw({base_word})"},
        "wildcard_search": {"query": f"kw({base_word[0]}u?{base_word[-1]})"},
        "double_wildcard_searches": {"query": f"kw(?{base_word[1]}?{base_word[-1]})"},
        "field_specific_keyword": {"query": f'kw(alternateName:"{base_word.capitalize()}")'},
    }


def generate_percentile_queries(
    small_percentile: float = DEFAULT_SMALL_PERCENTILE,
    high_percentile: float = DEFAULT_HIGH_PERCENTILE,
    small_thresholds: list[int] | None = None,
    large_thresholds: list[int] | None = None,
    operators: dict[str, list[str]] = DEFAULT_OPERATORS,
) -> dict[str, dict[str, Any]]:
    """
    Generate percentile queries for testing.

    Args:
        small_percentile: Percentile value for small thresholds
        high_percentile: Percentile value for large thresholds
        small_thresholds: List of small threshold values. If None, uses defaults
        large_thresholds: List of large threshold values. If None, uses defaults
        operators: Dictionary of operators to use for each threshold type
    """
    if small_thresholds is None:
        small_thresholds = DEFAULT_SMALL_THRESHOLDS
    if large_thresholds is None:
        large_thresholds = DEFAULT_LARGE_THRESHOLDS

    queries = {}

    # Generate small threshold queries
    for op in operators.get("small", ["le"]):
        for i, threshold in enumerate(small_thresholds, 1):
            queries[f"small_percentile_{op}_{i}"] = {
                "query": f"col(pp({small_percentile};{op};{threshold}))"
            }

    # Generate large threshold queries
    for op in operators.get("large", ["ge"]):
        for i, threshold in enumerate(large_thresholds, 1):
            queries[f"high_percentile_{op}_{i}"] = {
                "query": f"col(pp({high_percentile};{op};{threshold}))"
            }

    return queries


def generate_name_queries(
    column_names: list[str] = DEFAULT_COLUMN_NAMES,
    indices: list[int] = DEFAULT_INDICES,
    include_negations: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    Generate name queries for testing.

    Args:
        column_names: List of column names to generate queries for
        indices: List of indices to use in name queries
        include_negations: Whether to include NOT queries
    """
    queries = {}

    for col_name in column_names:
        for idx in indices:
            # Basic name query
            queries[f"name_{col_name}_{idx}"] = {"query": f"col(name({col_name}; {idx}))"}

            # Add negation if requested
            if include_negations:
                queries[f"not_name_{col_name}_{idx}"] = {
                    "query": f"col(NOT name({col_name}; {idx}))"
                }

    return queries


def wrap_term(term: str) -> str:
    """Wrap a term with appropriate function based on its type."""
    if "col(" in term:
        return term  # Already wrapped with col()
    if any(x in term for x in ["pp(", "name("]):
        return f"col({term})"
    return f"kw({term})" if not any(x in term for x in ["kw("]) else term


def generate_combined_queries() -> dict[str, dict[str, Any]]:
    """Generate queries that combine different types of base queries with logical operators."""
    queries = {}

    for combo_type, test_pairs in TEST_COMBINATIONS.items():
        for op in LOGICAL_OPERATORS:
            for idx, (term1, term2) in enumerate(test_pairs, 1):
                # Handle different types of terms
                term1_final = wrap_term(term1)
                term2_final = wrap_term(term2)

                query_name = f"combined_{combo_type}_{op.lower()}_{idx}"
                queries[query_name] = {"query": f"{term1_final} {op} {term2_final}"}

    return queries


def combine_column_queries(terms: list[str]) -> list[str]:
    """Combine multiple column queries into a single col() wrapper."""
    col_terms = []
    current_col_terms = []

    for term in terms:
        if term.startswith("col("):
            # Extract the inner part of col()
            inner = term[4:-1]
            current_col_terms.append(inner)
        elif any(x in term for x in ["pp(", "name("]):
            current_col_terms.append(term)
        else:
            # If we have accumulated col terms, combine them
            if current_col_terms:
                col_terms.append(f"col({' AND '.join(current_col_terms)})")
                current_col_terms = []
            col_terms.append(wrap_term(term))

    # Handle any remaining col terms
    if current_col_terms:
        col_terms.append(f"col({' AND '.join(current_col_terms)})")

    return col_terms


def generate_n_way_combined_queries() -> dict[str, dict[str, Any]]:
    """Generate queries that combine n terms with logical operators."""
    queries = {}

    for combo_type, term_lists in N_WAY_TEST_COMBINATIONS.items():
        for term_list in term_lists:
            n_terms = len(term_list)
            if n_terms > MAX_COMBINED_TERMS:
                continue

            # Generate different operator combinations
            for op in LOGICAL_OPERATORS:
                # Combine column queries and wrap other terms
                wrapped_terms = combine_column_queries(term_list)

                # Join terms with the operator
                query = f" {op} ".join(wrapped_terms)

                query_name = f"n_way_{combo_type}_{op.lower()}_{n_terms}terms"
                queries[query_name] = {"query": query}

                # Generate nested version
                if n_terms > 2:
                    nested_query = wrapped_terms[0]
                    for term in wrapped_terms[1:]:
                        nested_query = f"({nested_query} {op} {term})"

                    query_name = f"n_way_{combo_type}_{op.lower()}_{n_terms}terms_nested"
                    queries[query_name] = {"query": nested_query}

    return queries


def generate_all_test_cases() -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    return {
        "base_keyword_queries": {"queries": generate_base_keyword_queries()},
        "base_simple_keyword_queries": {
            "queries": generate_simple_keyword_queries(
                keywords=MEDICAL_KEYWORDS, prefix="medical_keyword", field_name="description"
            )
        },
        "base_keyword_queries_1": {"queries": generate_complex_keyword_queries("lung")},
        "base_keyword_queries_2": {"queries": generate_complex_keyword_queries("heart")},
        "base_percentile_queries": {
            "queries": generate_percentile_queries(
                small_percentile=0.25,
                high_percentile=0.75,
                small_thresholds=TEST_SMALL_THRESHOLDS,
                large_thresholds=TEST_LARGE_THRESHOLDS,
                operators=TEST_OPERATORS,
            )
        },
        "base_name_queries": {
            "queries": generate_name_queries(
                column_names=TEST_COLUMN_NAMES,  # customize columns
                indices=TEST_INDICES,  # customize indices
                include_negations=True,  # include NOT queries
            )
        },
        "combined_queries": {"queries": generate_combined_queries()},
        "n_way_combined_queries": {"queries": generate_n_way_combined_queries()},
    }


def save_test_cases(output_path: Path) -> None:
    """Generate test cases and save them to a JSON file."""
    test_cases = generate_all_test_cases()
    with output_path.open("w") as f:
        json.dump(test_cases, f, indent=2)


if __name__ == "__main__":
    output_dir = Path("test_cases")
    output_dir.mkdir(exist_ok=True)
    save_test_cases(output_dir / "performance_test_cases.json")
