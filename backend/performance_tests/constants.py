from typing import Final

# Keyword related constants
DEFAULT_KEYWORDS: Final[list[str]] = [
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

MEDICAL_KEYWORDS: Final[list[str]] = ["born", "death", "disease", "treatment"]

# Percentile related constants
DEFAULT_SMALL_THRESHOLDS: Final[list[int]] = [2000, 1000, 500, 200]
DEFAULT_LARGE_THRESHOLDS: Final[list[int]] = [1000000, 2000000, 3000000, 4000000]
DEFAULT_SMALL_PERCENTILE: Final[float] = 0.5
DEFAULT_HIGH_PERCENTILE: Final[float] = 0.9
DEFAULT_OPERATORS: Final[dict[str, list[str]]] = {"small": ["le"], "large": ["ge"]}

# Logical operators
#LOGICAL_OPERATORS: Final[list[str]] = ["AND", "OR", "XOR"]
LOGICAL_OPERATORS: Final[list[str]] = ["AND"]

# Name query related constants
DEFAULT_COLUMN_NAMES: Final[list[str]] = ["age", "height", "weight"]
DEFAULT_INDICES: Final[list[int]] = [0, 1, 2, 3]

# Test configuration
TEST_COLUMN_NAMES: Final[list[str]] = ["age", "height"]
TEST_INDICES: Final[list[int]] = [0, 3]
TEST_OPERATORS: Final[dict[str, list[str]]] = {
    "small": ["le", "lt"],  # Changed from ["le", "eq"] to valid operators
    "large": ["ge", "gt"],
}
TEST_SMALL_THRESHOLDS: Final[list[int]] = [100, 200, 300]
TEST_LARGE_THRESHOLDS: Final[list[int]] = [5000, 10000]

# Test combinations
TEST_COMBINATIONS: Final[dict[str, list[tuple[str, str]]]] = {
    "keyword_keyword": [("lung", "heart"), ("blood", "test"), ("germany", "italy")],
    "keyword_percentile": [("lung", "col(pp(0.5;lt;1000))"), ("heart", "col(pp(0.9;gt;1000000))")],
    "keyword_name": [("lung", "col(name(age; 0))"), ("heart", "col(name(height; 1))")],
    "percentile_name": [
        ("col(pp(0.5;le;1000))", "col(name(age; 0))"),
        ("col(pp(0.9;ge;1000000))", "col(name(height; 1))"),
    ],
}

# N-way test combinations
N_WAY_TEST_COMBINATIONS: Final[dict[str, list[list[str]]]] = {
    "keyword_chain": [
        ["lung", "heart", "blood"],
        ["germany", "italy", "usa", "france"],
        ["test", "study", "research", "analysis", "review"],
        [
            "lung",
            "heart",
            "blood",
            "test",
            "study",
            "research",
            "analysis",
            "review",
            "germany",
            "italy",
        ],
    ],
    "mixed_chain": [
        ["lung", "pp(0.5;lt;1000)", "name(age; 0)"],
        ["heart", "pp(0.9;gt;1000000)", "name(height; 1)"],
        ["blood", "pp(0.75;gt;500)", "name(weight; 2)", "pp(0.25;lt;100)"],
        [
            "lung",
            "pp(0.5;lt;1000)",
            "name(age; 0)",
            "heart",
            "pp(0.9;gt;1000000)",
            "name(height; 1)",
            "blood",
            "pp(0.75;gt;500)",
            "name(weight; 2)",
            "pp(0.25;lt;100)",
        ],
    ],
    "column_chain": [
        ["name(age; 0)", "name(height; 1)", "name(weight; 2)"],
        ["pp(0.25;lt;1000)", "pp(0.5;gt;2000)", "pp(0.75;lt;3000)"],
        [
            "name(age; 0)",
            "pp(0.25;lt;1000)",
            "name(height; 1)",
            "pp(0.5;gt;2000)",
            "name(weight; 2)",
            "pp(0.75;lt;3000)",
            "name(age; 3)",
            "pp(0.9;gt;4000)",
            "name(height; 4)",
            "pp(0.1;lt;500)",
        ],
    ],
    "mixed_column_keyword": [
        ["name(age; 0)", "pp(0.5;lt;1000)", "lung", "heart"],
        [
            "name(age; 0)",
            "pp(0.25;lt;500)",
            "name(weight; 2)",
            "lung",
            "heart",
            "blood",
            "pp(0.75;gt;3000)",
            "name(height; 1)",
            "test",
            "study",
        ],
    ],
}

# Maximum number of terms to combine
MAX_COMBINED_TERMS: Final[int] = 10
