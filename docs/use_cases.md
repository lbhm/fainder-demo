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
      - big config: **2 sec**
      - middle config: **2.45 sec**
      - small config: **2.54 sec**
      - bad_3 config: **3 sec**

   → **with full_recall:**
      - big config: **18** results
      - middle config: **18** results
      - small config: **18** results
      - bad_3 config: **63** results

   → **with full_precision:**
      - big config: **0** results
      - middle config: **0** results
      - small config: **0** results
      - bad_3 config: **0** results

---

## Cardiovascular

### Queries and Results:

1. `KW('Cardiovascular')`
   → approx. **200** results

2. `KW('Cardiovascular') AND col(name("age"; 3))`
   → approx. **100** results

3. `KW('Cardiovascular') AND col(name("age"; 3) AND pp(0.75; le; 45))`
   → **with exact:** 11 results
   → **Runtime:**
      - big config: **1.7 sec**
      - middle config: **2.4 sec**
      - small config: **2.45 sec**
      - bad_3 config: **2.9 sec**

   → **with full_recall:**
      - big config: **11** results
      - middle config: **11** results
      - small config: **12** results
      - bad_3 config: **42** results

   → **with full_precision:**
      - big config: **10** results
      - middle config: **10** results
      - small config: **10** results
      - bad_3 config: **10** results


## Cars

### Queries and Results:

1. `KW('"Car"')`
   → approx. **2,300** results

2. `KW('"Car"') AND col(name("price"; 0))`
   → approx. **460** results

3. `KW('"Car"') AND col(name("price"; 0) AND pp(1.0; le; 9000))`
   → **with exact:** 29 results
   → **Runtime:**
      - big config: **1 sec**
      - middle config: **1.3 sec**
      - small config: **1.3 sec**
      - bad_3 config: **1.8 sec**

   → **with full_recall:**
      - big config: **33** results
      - middle config: **42** results
      - small config: **33** results
      - bad_3 config: **69** results

   → **with full_precision:**
      - big config: **14** results
      - middle config: **14** results
      - small config: **14** results
      - bad_3 config: **14** results


## Loans

### Queries and Results:

1. `KW('"loan"')`
   → approx. **1100** results

2. `KW('"loan"') AND col(name("income";0))`
   → approx. **45** results

3. `KW('"loan"') AND col(name("income";0) AND pp(0.4;le;15000))`
   → **with exact:**  28 results
   → **Runtime:**
      - big config: **1.8 sec**
      - middle config: **1.9 sec**
      - small config: **1.9 sec**
      - bad_3 config: **2.3 sec**

   → **with full_recall:**
      - big config: **28** results
      - middle config: **28** results
      - small config: **28** results
      - bad_3 config: **39** results

   → **with full_precision:**
      - big config: **13** results
      - middle config: **13** results
      - small config: **13** results
      - bad_3 config: **13** results


## Air quality

### Queries and Results:

1. `KW('"air quality"')`
   → approx. **480** results

2. `KW('"air quality"') AND col(name("no2";0))`
   → approx. **31** results

3. `KW('"air quality"') AND col(name("no2";0) AND pp(0.2; ge; 100))`
   → **with exact:**  4 results
   → **Runtime:**
      - big config: **1.9 sec**
      - middle config: **2.0 sec**
      - small config: **2.1 sec**
      - bad_3 config: **2.6 sec**

   → **with full_recall:**
      - big config: **5** results
      - middle config: **6** results
      - small config: **7** results
      - bad_3 config: **8** results

   → **with full_precision:**
      - big config: **2** results
      - middle config: **2** results
      - small config: **2** results
      - bad_3 config: **1** results


## Student performance

### Queries and Results:

1. `KW('"student performance"')`
   → approx. **260** results

2. `KW('"student performance"') AND col(name('"math score"';2))`
   → approx. **50** results

3. `KW('"student performance"') AND col(name('"math score"';2) AND pp(0.25; lt; 50))`
   → **with exact:** 5 results
   → **Runtime:**
      - big config: **2.8 sec**
      - middle config: **2.9 sec**
      - small config: **2.9 sec**
      - bad_3 config: **3.7 sec**

   → **with full_recall:**
      - big config: **46** results
      - middle config: **46** results
      - small config: **46** results
      - bad_3 config: **49** results

   → **with full_precision:**
      - big config: **1** results
      - middle config: **1** results
      - small config: **1** results
      - bad_3 config: **0** results
