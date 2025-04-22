# ruff: noqa: E501, RUF001
from typing import TypedDict

import numpy as np

from backend.config import Highlights


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
                        "\nIt includes rainfall amounts, temperatures, humidity levels, and other geographical and climatic details, making it ideal for analyzing <mark>weather</mark> patterns, climate change, and their impacts across different regions.\n"
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
    "test_simple_kw_2": {
        "query": "kw('data')",
        "expected": (
            {
                0: {
                    "description": (
                        "\n**This dataset, provides detailed weather and climate statistics for major cities in Germany from 2015 to 2023.** \n"
                        "\nIt includes rainfall amounts, temperatures, humidity levels, and other geographical and climatic details, making it ideal for analyzing weather patterns, climate change, and their impacts across different regions.\n"
                        "\n1. **City:** Name of the city.\n"
                        "\n2. **Latitude:** City's latitude in degrees.\n"
                        "\n3. **Longitude:** City's longitude in degrees.\n"
                        "\n4. **Month:** The month number (1-12).\n"
                        "\n5. **Year:** The year of the <mark>data</mark>.\n"
                        "\n6. **Rainfall (mm):** Rainfall amount in millimeters.\n"
                        "\n7. **Elevation (m):** City’s elevation above sea level in meters.\n"
                        "\n8. **Climate_Type:** The climate classification of the city.\n"
                        "\n9. **Temperature (°C):** Average temperature for the month in Celsius.\n"
                        "\n10. **Humidity (%):** Average humidity level for the month in percentage.\n"
                        "\n"
                    ),
                    "name": "Germany City Rainfall <mark>Data</mark>",
                },
                1: {
                    "description": "Avacado Project\nProblem Statement:\nAvocado is a fruit consumed by people heavily in the United States. \n\nContent\nThis <mark>data</mark> was downloaded from the Hass Avocado Board website in May of 2018 & compiled into a single CSV. \n\nThe table below represents weekly 2018 retail scan <mark>data</mark> for National retail volume (units) and price. Retail scan <mark>data</mark> comes directly from retailers\u2019 cash registers based on actual retail sales of Hass avocados. \n\nStarting in 2013, the table below reflects an expanded, multi-outlet retail da<mark>ta s</mark>et. Multi-outlet reporting includes an aggregation of the following channels: grocery, mass, club, drug, dollar and military. The Average Price (of avocados) in the table reflects a per unit (per avocado) cost, even when multiple units (avocados) are sold in bags. \n\nThe Product Lookup codes (PLU\u2019s) in the table are only for Hass avocados. Other varieties of avocados (e.g. greenskins) are not included in this table.",
                    "keywords": "<mark>data</mark> type > tabular; <mark>data</mark> type > categorical; subject > earth and nature > environment > agriculture; geography and places > north america > united states; task > regression",
                },
                2: {
                    "description": "### Background\nWhat can we say about the success of a movie before it is released? Are there certain companies (Pixar?) that have found a consistent formula? Given that major films costing over $100 million to produce can still flop, this question is more important than ever to the industry. Film aficionados might have different interests. Can we predict which films will be highly rated, whether or not they are a commercial success?\n\nThis is a great place to start digging in to those questions, with <mark>data</mark> on the plot, cast, crew, budget, and revenues of several thousand films.\n\n### <mark>Data</mark> Source Transfer Summary\nWe (Kaggle) have removed the original version of this dataset per a [DMCA](https://en.wikipedia.org/wiki/Digital_Millennium_Copyright_Act) takedown request from IMDB. In order to minimize the impact, we're replacing it with a similar set of films and <mark>data</mark> fields from [The Movie Database (TMDb)](themoviedb.org) in accordance with [their terms of use](https://www.themoviedb.org/documentation/api/terms-of-use). The bad news is that kernels built on the old dataset will most likely no longer work.\n\nThe good news is that:\n\n- You can port your existing kernels over with a bit of editing. [This kernel](https://www.kaggle.com/sohier/getting-imdb-kernels-working-with-tmdb-<mark>data</mark>/) offers functions and examples for doing so. You can also find [a general introduction to the new format here](https://www.kaggle.com/sohier/tmdb-format-introduction).\n\n- The new dataset contains full credits for both the cast and the crew, rather than just the first three actors.\n\n- Actor and actresses are now listed in the order they appear in the credits. It's unclear what ordering the original dataset used; for the movies I spot checked it didn't line up with either the credits order or IMDB's stars order.\n\n- The revenues appear to be more current. For example, IMDB's figures for Avatar seem to be from 2010 and understate the film's global revenues by over $2 billion.\n\n- Some of the movies that we weren't able to port over (a couple of hundred) were just bad entries. For example, [this IMDB entry](http://www.imdb.com/title/tt5289954/?ref_=fn_t...) has basically no accurate information at all. It lists Star Wars Episode VII as a documentary.\n\n### <mark>Data</mark> Source Transfer Details\n\n- Several of the new columns contain json. You can save a bit of time by porting the load <mark>data</mark> functions [from this kernel]().\n\n- Even in simple fields like runtime may not be consistent across versions. For example, previous dataset shows the duration for Avatar's extended cut while TMDB shows the time for the original version.\n\n- There's now a separate file containing the full credits for both the cast and crew.\n\n- All fields are filled out by users so don't expect them to agree on keywords, genres, ratings, or the like.\n\n- Your existing kernels will continue to render normally until they are re-run.\n\n- If you are curious about how this dataset was prepared, the code to access TMDb's API is posted [here](https://gist.github.com/SohierDane/4a84cb96d220fc4791f52562be37968b).\n\nNew columns:\n\n- homepage\n\n- id\n\n- original_title\n\n- overview\n\n- popularity\n\n- production_companies\n\n- production_countries\n\n- release_date\n\n- spoken_languages\n\n- status\n\n- tagline\n\n- vote_average\n\nLost columns:\n\n- actor_1_facebook_likes\n\n- actor_2_facebook_likes\n\n- actor_3_facebook_likes\n\n- aspect_ratio\n\n- cast_total_facebook_likes\n\n- color\n\n- content_rating\n\n- director_facebook_likes\n\n- facenumber_in_poster\n\n- movie_facebook_likes\n\n- movie_imdb_link\n\n- num_critic_for_reviews\n\n- num_user_for_reviews\n\n### Open Questions About the <mark>Data</mark>\nThere are some things we haven't had a chance to confirm about the new dataset. If you have any insights, please let us know in the forums!\n\n- Are the budgets and revenues all in US dollars? Do they consistently show the global revenues?\n\n- This dataset hasn't yet gone through a <mark>data</mark> quality analysis. Can you find any obvious corrections? For example, in the IMDb version it was necessary to treat values of zero in the budget field as missing. Similar findings would be very helpful to your fellow Kagglers! (It's probably a good idea to keep treating zeros as missing, with the caveat that missing budgets much more likely to have been from small budget films in the first place).\n\n### Inspiration\n\n- Can you categorize the films by type, such as animated or not? We don't have explicit labels for this, but it should be possible to build them from the crew's job titles.\n\n- How sharp is the divide between major film studios and the independents? Do those two groups fall naturally out of a clustering analysis or is something more complicated going on?\n\n### Acknowledgements\nThis dataset was generated from [The Movie Database](themoviedb.org) API. This product uses the TMDb API but is not endorsed or certified by TMDb.\nTheir API also provides access to <mark>data</mark> on many additional movies, actors and actresses, crew members, and TV shows. You can [try it for yourself here](https://www.themoviedb.org/documentation/api).\n\n![](https://www.themoviedb.org/assets/static_cache/9b3f9c24d9fd5f297ae433eb33d93514/images/v4/logos/408x161-powered-by-rectangle-green.png)\n\n"
                },
            },
            set(),
        ),
    },
    "test_simple_pp": {
        "query": "col(pp(0.1;ge;1))",
        "expected": (
            {},
            {
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
                np.uint32(28),
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
                        "\nIt includes rainfall amounts, temperatures, humidity levels, and other geographical and climatic details, making it ideal for analyzing <mark>weather</mark> patterns, climate change, and their impacts across different regions.\n"
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
