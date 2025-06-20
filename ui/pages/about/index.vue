<!--
  This is a placeholder for the about page.
-->

<template>
  <v-main>
    <v-divider />
    <div class="pa-5">
      <h1 class="mb-6">About</h1>
      <p class="mb-4">
        Fainder is a system designed to search for tabular datasets from the
        Kaggle website. <br />
        It leverages the recently developed Fainder Index to enable advanced
        search capabilities, including percentile predicate-based queries.
      </p>

      <h2 class="mb-4">Operations</h2>
      <p class="mb-4">
        There are multiple search operations which can all be combined using the
        standard logical operations "<code>AND</code>", "<code>OR</code>" and
        "<code>NOT</code>". <br />
        One can use operations to look for certain general dataset properties or
        properties of columns in a dataset.
      </p>

      <h3 class="mb-4">Dataset Operations</h3>
      <h4 class="mb-4">Keyword Operator</h4>
      <p class="mb-4">
        We provide the keyword operation, written as
        <code>kw('&lt;query&gt;')</code>, to look for datasets with a certain
        name according to the query. <br />
        One can use the <code>*</code> wildcard to allow more freedom in the
        name, such as 'A*' to look for datasets which start with an A. <br />
        The logical operations can also be used inside to allow for queries such
        as <code>kw('data AND (weather OR avocado)')</code>.
      </p>

      <h3 class="mb-4">Column Operations</h3>
      <p class="mb-4">
        All column operations must be inside
        <code>col(&lt;operations&gt;)</code>. <br />
        We provide the 2 column operations
        <code>name('&lt;query&gt;'; &lt;topk-nearest&gt;)</code> and
        <code>pp(&lt;percentile&gt;; &lt;comparison&gt;; &lt;value&gt;)</code>.
      </p>

      <h4 class="mb-4">Name Operator</h4>
      <p class="mb-4">
        The name operator can be used to look for datasets which have at least
        one column with the name <code>&lt;query&gt;</code> or something similar
        to it. <br />
        The second argument <code>&lt;topk-nearest&gt;</code> is a number and
        allows for including the top-k nearest finds according to semantic
        similarity. Using 0 leads to an exact search.
      </p>
      <p class="mb-4">
        Example: <code>col(name('age'; 2))</code> looks for datasets with a
        column with the name "age" or the 2 closest semantic finds to "age".
      </p>

      <h4 class="mb-4">Percentile Predicate (pp) Operator</h4>
      <p class="mb-4">
        The pp operator can be used to look for certain distributions of values
        in columns using percentile predicates and is particularly useful in
        combination with the name operator. <br />
        <code>&lt;percentile&gt;</code> is a number between 0 and 1 and decides
        how much percent of the values must fulfill the comparison. <br />
        <code>&lt;comparison&gt;</code> is the comparison for the percentile
        predicate. One can use <code>"ge"</code> for greater or equal, or
        <code>"le"</code> for less or equal. <br />
        <code>&lt;value&gt;</code> decides the value to compare all the column
        values against and can be any number.
      </p>
      <p class="mb-4">
        Example: <code>col(pp(0.9; ge; 100))</code> looks for datasets with a
        column where 90% percent of the values are greater or equal than 100.
      </p>
    </div>
  </v-main>
</template>
