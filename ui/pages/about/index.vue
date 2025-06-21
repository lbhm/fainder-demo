<!--
  This about page contains a summary of the system and its query language.
-->

<template>
  <v-main>
    <v-divider />
    <div class="pa-5 mx-auto" style="max-width: 800px">
      <h1>About</h1>
      <p>
        Fainder is a metadata-based dataset search engine that combines
        traditional keyword search with advanced search operators. It introduces
        the novel Dataset Query Language (DQL), which allows users to perform
        complex dataset search queries, including percentile predicates and
        semantic similarity searches.
      </p>
      <p>
        The system leverages a recently developed
        <a href="https://github.com/lbhm/fainder">index</a>
        to enable distribution-aware search.
      </p>

      <h2>DQL Operators</h2>
      <p>
        The Dataset Query Language (DQL) is a declarative query language built
        around Boolean algebtra. The basic operators <code>AND</code>,
        <code>OR</code> and <code>NOT</code> can be used to compose queries.<br />
        Beyond the basic operators, DQL provides dataset-level and column-level
        operators. Dataset operators search for general dataset properties,
        while column operators focus on specific columns in a dataset.
      </p>
      <p>
        All DQL operators are case-insentive and usually have a long as well as
        a short form.<br />
        Strings must be enclosed in single or double quotes.
      </p>

      <h3>Dataset Operators</h3>

      <h4>Keyword Search</h4>
      <p>
        The <code>KEYWORD</code> or <code>KW</code> operator allows you to
        search through the textual descriptions of datasets and supports the
        full Tantivy query language. <br />
        The query can be a simple keyword, such as <code>KW('weather')</code>,
        which will return datasets that contain the word "weather" in their
        description or title. <br />
        Alternatively, you can use more complex queries to search for datasets
        with specific keywords or combinations of keywords. <br />
        For example, <code>KW('weather AND avocado')</code> will return datasets
        that contain both "weather" and "avocado" in their description. You can
        use the <code>*</code> wildcard to allow for more freedom in the name,
        such as <code>KW('A*')</code> to look for datasets that start with an A.
      </p>

      <h3>Column Operators</h3>
      <p>
        In order to search for specific columns in datasets, use the
        <code>COLUMN</code> or <code>COL</code> operator. This operator allows
        you to specify conditions on the columns of datasets, such as column
        names or value distributions.
      </p>
      <p>
        Usage:
        <code>COL(&lt;operations&gt;)</code>
      </p>
      <p>
        The following operators can be used to specify conditions on columns.
      </p>

      <h4>Column Name Search</h4>
      <p>
        The column name operator can be used to search for datasets that contain
        columns max-width with specific names or similar names. <br />
      </p>
      <p>
        Usage: <code>NAME(&lt;search_term&gt;; &lt;num_neighbors&gt;)</code
        ><br />
        Setting <code>num_neighbors</code> to 0 will only return exact matches.
      </p>

      <h4>Percentile Predicates</h4>
      <p>
        The <code>PERCENTILE</code> or <code>PP</code> operator allows you to
        search for datasets based on the distribution of values in specific
        columns. It is particularly useful for identifying datasets with certain
        statistical properties and when combined with the column name operator.
      </p>
      <p>
        Usage:
        <code
          >PP(&lt;percentile&gt;; &lt;comparison&gt;;
          &lt;reference_value&gt;)</code
        ><br />
        <code>&lt;percentile&gt;</code> is a number between 0 and 1 and decides
        how many percent of a column's values must fulfill the comparison.
        <br />
        <code>&lt;comparison&gt;</code> is the comparison for the percentile
        predicate. One can use <code>ge</code> for greater or equal, or
        <code>le</code> for less or equal. <br />
        <code>&lt;value&gt;</code> decides the value to compare all the column
        values against and can be any number.
      </p>
      <p>
        Example: <code>COL(PP(0.9; ge; 100))</code> searches for datasets with a
        column where at least 90% percent of the values are greater or equal
        than 100.
      </p>

      <h2>Example Queries</h2>
      <p>Here are some example queries to illustrate the use of DQL:</p>
      <ul>
        <li>
          <code>KW('weather')</code><br />
          Find datasets related to weather.
        </li>
        <li>
          <code>COL(NAME('age'; 2))</code><br />
          Find datasets with a column named "age" or the 2 closest semantic
          finds to "age".
        </li>
        <li>
          <code>
            KEYWORD(“lung cancer”) OR KEYWORD(“breast cancer”) AND COLUMN(
            NAME(”age”;5) AND PERCENTILE(0.5;ge;60) ) AND COLUMN(
            NAME(“gender”;0) OR NAME(“sex”;0) ) AND COLUMN( NAME(“diagnosis”;5)
            ) </code
          ><br />
          Example of a more complex query combining multiple operators.
        </li>
      </ul>
    </div>
  </v-main>
</template>

<style scoped>
h1 {
  font-size: 2em;
  margin-bottom: 16px;
}

h2 {
  font-size: 1.5em;
  margin-bottom: 12px;
}

h3 {
  font-size: 1.25em;
  margin-bottom: 8px;
}

h4 {
  margin-bottom: 8px;
}

p {
  margin-bottom: 16px;
}

code {
  font-family: monospace;
  background-color: #f4f4f4;
  color: #333;
  padding: 2px 4px;
  border-radius: 4px;
}

@media (prefers-color-scheme: dark) {
  code {
    background-color: #23272e;
    color: #e6e6e6;
  }
}
</style>
