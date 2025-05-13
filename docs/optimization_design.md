# Engine Design and Optimization

## General Design

The engine consists of three main components:

- Parser → Creates an AST from the query using the DQL query language
- Optimizer → Applies selected optimization strategies to the AST
- Executor → Executes the optimized AST and returns the results

## Parser

We use the `lark` library to parse DQL into an AST.

## Optimizer

We have implemented the following optimization strategies:

### Keyword Merging

- Merges multiple keywords into a single keyword when they are on the same level on the AST
- Example: `kw('keyword1') AND kw('keyword2')` → `kw('keyword1 AND keyword2')`
- This results in a significant performance improvement as we can search for a single keyword instead of multiple keywords

### Cost-based Sorting

- Sorts the AST based on the estimated cost of the operations
- Operation order: Keyword → Column name Predicate → Percentile Predicate

## Executor

### Sequential Executor

Sequentially executes the AST using a bottom-up approach to evaluate the AST.

### Prefilter Executor

The Prefilter Executor provides significant optimizations for queries involving percentile predicates.

#### Key Features

- Optimizes evaluation of Percentile Predicates using filters
- Requires cost-based sorting and keyword merging before read-and-write group creation
- Creates read and write groups before query execution:
  - Read groups: Set of intermediary results used as filter for leaf nodes
  - Write groups: Storage location for leaf node results

#### Read-and-Write Group Rules

Using a top-down approach:

1. **Disjunction nodes**: Each child gets
   - A new write group
   - Same read group as parent plus its own write group
2. **Conjunction nodes**: Each child gets
   - Same write group as parent
   - Same read group as parent
3. **Negation nodes**:
   - Create new write group
   - Pass as both write and read group to children

#### Performance Impact

- Reduces execution time from ~20s to 0.5s for queries combining percentile predicates with keyword/column predicates
- Negligible overhead for queries without percentile predicates
- Optimal for the expected use case (percentile + keyword/column predicates)

### Threaded Executor
The Threaded Executor provides parallel execution capabilities for query processing.

#### Key Features
- Utilizes `concurrent.futures` library for thread pool management
- Requires cost-based sorting and keyword merging before execution
- Executes AST nodes in parallel using different threads

#### Performance Characteristics
- Significant performance improvement for percentile predicates without keyword/column filters, when compared to the sequential or prefilter executor
- Negligible overhead for single-predicate queries
- Less efficient in cases where filtering could be used
- Limited parallel execution due to Python's GIL (Global Interpreter Lock)

### Threaded Executor with Prefilter
This executor combines the benefits of both threading and prefiltering approaches.

#### Key Features
- Integrates threading capabilities with prefilter optimization
- Requires cost-based sorting and keyword merging before execution
- Hybrid approach:
  - Uses threading for all leaf nodes
  - Combines and resolves for filter construction for percentile predicates all relevant nodes except other percentile predicates

#### Performance Characteristics
- Combines advantages of both threaded and prefilter executors
- Negligible overhead for single-predicate queries
- Optimal performance for complex queries involving multiple predicates
