# Use Cases

Use cases for the dsl and comparison of different configurations.

## Lung Cancer

### Queries and Results:

1. `KW('"lung cancer"')`
   → approx. **100** results

2. `KW('"lung cancer"') AND col(name("age"; 0))`
   → approx. **10** results

3. `KW('"lung cancer"') AND col(name("age"; 4))`
   → approx. **70** results

4. `KW('"lung cancer"') AND col(name("age"; 4) AND pp(0.7; le; 50))`
   → **with exact:** 18 results
   → **Runtime:**
      - good config: **2 sec**
      - bad config: **3 sec**

   → **with full_recall:**
      - good config: **18** results
      - bad config: **63** results

   → **with full_precision:**
      - good config: **0** results
      - bad config: **0** results

---

## Cardiovascular

### Queries and Results:

1. `KW('Cardiovascular')`
   → approx. **200** results

2. `KW('Cardiovascular') AND col(name("age"; 3))`
   → approx. **100** results

3. `KW('Cardiovascular') AND col(name("age"; 3) AND pp(0.75; le; 45))`
   → **with exact:** 11 results

   → **with full_recall:**
      - good config: **11** results
      - bad config: **42** results

   → **with full_precision:**
      - good config: **10** results
      - bad config: **10** results


## Cars

### Queries and Results:

1. `KW('"Car"')`
   → approx. **2,300** results

2. `KW('"Car"') AND col(name("price"; 0))`
   → approx. **460** results

3. `KW('"Car"') AND col(name("price"; 0) AND pp(1.0; le; 9000))`
   → **with exact:** 29 results
   → **Runtime:**
      - good config: **1 sec**
      - bad config: **1.2 sec**

   → **with full_recall:**
      - good config: **33** results
      - bad config: **69** results

   → **with full_precision:**
      - good config: **14** results
      - bad config: **14** results
