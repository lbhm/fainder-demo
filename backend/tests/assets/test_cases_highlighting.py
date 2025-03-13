# ruff: noqa: E501, RUF001
from typing import TypedDict

import numpy as np

from backend.engine.executor import Highlights


class HighlightingCase(TypedDict):
    query: str
    expected: Highlights


HIGHLIGHTING_CASES: dict[str, HighlightingCase] = {
    "test_simple_kw": {
        "query": "kw('weather')",
        "expected": (
            {
                0: {
                    "keywords": "subject > earth and nature > environment > <mark>weather</mark> and climate; language > german",
                    "description": (
                        "\n**This dataset, provides detailed <mark>weather</mark> and climate statistics for major cities in Germany from 2015 to 2023.** \n"
                        "\nIt includes rainfall amounts, temperatures, humidity levels, and other geographical and climatic details, making it ideal for analyzing weather patterns, climate change, and their impacts across different regions.\n"
                        "\n1. **City:** Name of the city.\n"
                        "\n2. **Latitude:** City's latitude in degrees.\n"
                        "\n3. **Longitude:** City's longitude in degrees.\n"
                        "\n4. **Month:** The month number (1-12).\n"
                        "\n5. **Year:** The year of the data.\n"
                        "\n6. **Rainfall (mm):** Rainfall amount in millimeters.\n"
                        "\n7. **Elevation (m):** City’s elevation above sea level in meters.\n"
                        "\n8. **Climate_Type:** The climate classification of the city.\n"
                        "\n9. **Temperature (°C):** Average temperature for the month in Celsius.\n"
                        "\n10. **Humidity (%):** Average humidity level for the month in percentage.\n"
                        "\n"
                    ),
                    "alternateName": "<mark>Weather</mark> Patterns Rainfall and Climate German Cities",
                }
            },
            set(),
        ),
    },
    "test_simple_pp": {
        "query": "col(pp(0.1;ge;1))",
        "expected": (
            {},
            {
                np.uint32(1),
                np.uint32(2),
                np.uint32(3),
                np.uint32(4),
                np.uint32(5),
                np.uint32(6),
                np.uint32(8),
                np.uint32(9),
                np.uint32(10),
                np.uint32(12),
                np.uint32(13),
                np.uint32(14),
                np.uint32(15),
                np.uint32(16),
                np.uint32(17),
                np.uint32(18),
                np.uint32(19),
                np.uint32(20),
                np.uint32(22),
                np.uint32(24),
                np.uint32(28),
                np.uint32(31),
                np.uint32(36),
                np.uint32(40),
                np.uint32(41),
                np.uint32(46),
                np.uint32(47),
            },
        ),
    },
    "test_simple_col_name": {
        "query": "col(name('movie_id'; 0))",
        "expected": ({}, {np.uint32(24)}),
    },
    "test_kw_in_name_field": {
        "query": "kw('name:(germany)')",
        "expected": (
            {0: {"name": "<mark>Germany</mark> City Rainfall Data"}},
            set(),
        ),
    },
    "test_kw_in_keywords_field": {
        "query": "kw('keywords:(environment)')",
        "expected": (
            {
                0: {
                    "keywords": "subject > earth and nature > <mark>environment</mark> > weather and climate; language > german"
                },
                1: {
                    "keywords": "data type > tabular; data type > categorical; subject > earth and nature > <mark>environment</mark> > agriculture; geography and places > north america > united states; task > regression"
                },
            },
            set(),
        ),
    },
    "test_kw_in_creator_field": {
        "query": "kw('creator:(Ayush Yadav)')",
        "expected": (
            {1: {"creator-name": "<mark>Ayush</mark> <mark>Yadav</mark>"}},
            set(),
        ),
    },
    "test_simple_pp_and_kw": {
        "query": "col(pp(0.1;ge;1)) AND kw('weather')",
        "expected": (
            {
                0: {
                    "keywords": "subject > earth and nature > environment > <mark>weather</mark> and climate; language > german",
                    "description": (
                        "\n**This dataset, provides detailed <mark>weather</mark> and climate statistics for major cities in Germany from 2015 to 2023.** \n"
                        "\nIt includes rainfall amounts, temperatures, humidity levels, and other geographical and climatic details, making it ideal for analyzing weather patterns, climate change, and their impacts across different regions.\n"
                        "\n1. **City:** Name of the city.\n"
                        "\n2. **Latitude:** City's latitude in degrees.\n"
                        "\n3. **Longitude:** City's longitude in degrees.\n"
                        "\n4. **Month:** The month number (1-12).\n"
                        "\n5. **Year:** The year of the data.\n"
                        "\n6. **Rainfall (mm):** Rainfall amount in millimeters.\n"
                        "\n7. **Elevation (m):** City’s elevation above sea level in meters.\n"
                        "\n8. **Climate_Type:** The climate classification of the city.\n"
                        "\n9. **Temperature (°C):** Average temperature for the month in Celsius.\n"
                        "\n10. **Humidity (%):** Average humidity level for the month in percentage.\n"
                        "\n"
                    ),
                    "alternateName": (
                        "<mark>Weather</mark> Patterns Rainfall and Climate German Cities"
                    ),
                }
            },
            {
                np.uint32(1),
                np.uint32(2),
                np.uint32(3),
                np.uint32(4),
                np.uint32(5),
                np.uint32(6),
                np.uint32(8),
                np.uint32(9),
            },
        ),
    },
}
