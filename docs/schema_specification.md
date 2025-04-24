# Schema Specification

In this document, we describe how we extend the Croissant specification with additional fields, especially those that we expect to be provided externally and those that we create internally.

## External Fields

- We expect Croissant metadata with a `recordSet` key and the following fields in the records depending on the value of the field `dataType`:
  - Numeric fields: The key `histogram` containing the key `bins` and the key `densities` each with a list of numbers and the key `statistics` with the keys `count`, `mean`, `std`, `min`, `25%`, `50%`, `75%` and `max` each with a numerical value.
  - Text fields: The key `n_unique` with a number and `most_common` with 10 keys and a number each referring to the frequency of the key.
  - Boolean fields: A key `count` containing two keys which count the posiive and negative occurrences with integers as values.
  - Date fields: The keys `min_date`, `max_date` with a string in the ISO 8601 format as a value each and the key `unique_dates` with an integer as a value.
- Usability score: The key `usability` with a numeric value between 0 and 1 in the top level hierarchy.

## Internal Fields

We extend the Croissant metadata with the following information during our indexing:

- We create an `id` key in the top level hierarchy with a non-negative integer as a value.
- For every field in every record of the `recordSet` we add another `id` key for the columns of the tabular data with a non-negative integer as a value.
  - If there is a `histogram` key in the field, we also insert an `id` key into the histogram object with the same value type as above.

All `id` keys are unique and assigned independently of the other keys (e.g., dataset `id`s are not related to column `id`s).
