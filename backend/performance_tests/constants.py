from typing import Final

# Keyword related constants
DEFAULT_KEYWORDS: Final[list[str]] = [
    "test",
    "born",
    "by",
    "blood",
    "heart",
    "lung",
    "test",
    "germany",
    "italy",
    "usa",
    "bank",
]


# Percentile related constants
DEFAULT_SMALL_THRESHOLDS: Final[list[int]] = [2000, 1000, 500, 200]
DEFAULT_LARGE_THRESHOLDS: Final[list[int]] = [1000000, 2000000, 3000000, 4000000]
DEFAULT_SMALL_PERCENTILE: Final[float] = 0.5
DEFAULT_HIGH_PERCENTILE: Final[float] = 0.9
DEFAULT_OPERATORS: Final[dict[str, list[str]]] = {"small": ["le"], "large": ["ge"]}

# Logical operators
# LOGICAL_OPERATORS: Final[list[str]] = ["AND", "OR", "XOR"]
LOGICAL_OPERATORS: Final[list[str]] = ["AND"]

# Maximum number of terms to combine
MAX_COMBINED_TERMS: Final[int] = 10
