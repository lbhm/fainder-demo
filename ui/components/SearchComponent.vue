# Search page for datasets search by precentile predicates and search by key
words # The search page will contain multiple search bars

<template>
  <v-main :class="['search-main', { 'pa-3': inline }]">
    <v-container :class="{ 'pa-2': inline }">
      <v-row :class="{ 'inline-layout': inline }">
        <v-col cols="11">
          <div class="input-wrapper">
            <v-textarea
              v-model="searchQuery"
              label="Search"
              variant="outlined"
              density="comfortable"
              :error="!isValid"
              :rules="[validateSyntax]"
              :hide-details="true"
              :rows="current_rows"
              class="search-input"
              append-inner-icon="mdi-magnify"
              :auto-grow="true"
              autofocus
              @update:model-value="highlightSyntax"
              @keydown="handleKeyDown"
              @focus="isSearchFocused = true"
              @blur="isSearchFocused = false"
              @click:append-inner="searchData"
            />
            <div class="syntax-highlight" v-html="highlightedQuery" />
            <div v-if="syntaxError" class="error-message">
              {{ syntaxError }}
            </div>
          </div>
        </v-col>
        <v-col cols="1">
          <v-btn
            icon="mdi-cog"
            variant="text"
            elevation="0"
            density="compact"
            class="ml-2"
            @click="showSettings = true"
          />
        </v-col>
      </v-row>

      <!-- Simple Query Builder Toggle Button -->
      <v-row v-if="simpleBuilder" class="mt-1">
        <v-col cols="12">
          <v-btn
            v-if="!showSimpleBuilder"
            prepend-icon="mdi-plus"
            elevation="0"
            @click="showSimpleBuilder = true"
          >
            Add Column Filters
          </v-btn>
        </v-col>
      </v-row>

      <!-- Simple Query Builder -->
      <v-expand-transition>
        <v-row
          v-if="simpleBuilder && showSimpleBuilder"
          class="query-builder mt-4"
        >
          <v-col cols="12">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="builder-header">
                <span class="text-h5">Query Builder</span>
              </div>
              <v-btn
                variant="text"
                icon="mdi-close"
                size="small"
                @click="showSimpleBuilder = false"
              />
            </div>

            <!-- Combined filters list -->
            <v-chip-group class="mb-4" column>
              <v-chip
                v-for="(term, index) in searchTerms"
                :key="index"
                closable
                :color="
                  term.type === 'column'
                    ? 'primary'
                    : term.type === 'percentile'
                      ? 'indigo'
                      : 'success'
                "
                @click:close="removeSearchTerm(index)"
                @click="transferTerm(term, index)"
              >
                <template v-if="term.type === 'column'">
                  COLUMN(NAME({{ term.column }};{{ term.threshold }}))
                </template>
                <template v-else-if="term.type === 'percentile'">
                  COLUMN(PERCENTILE({{ term.percentile }};{{
                    term.comparison
                  }};{{ term.value }}))
                </template>
                <template v-else>
                  COLUMN(NAME({{ term.column }};{{ term.threshold }}) AND
                  PERCENTILE({{ term.percentile }};{{ term.comparison }};{{
                    term.value
                  }}))
                </template>
              </v-chip>
            </v-chip-group>

            <!-- Split into separate rows -->
            <v-row>
              <v-col cols="12">
                <div class="text-subtitle-1 mb-2">Column Name Predicate</div>
                <v-row>
                  <v-col cols="5">
                    <v-text-field
                      v-model="columnFilter.column"
                      label="Column Name"
                      variant="outlined"
                      density="comfortable"
                      hide-details="auto"
                    />
                  </v-col>
                  <v-col cols="5">
                    <v-text-field
                      v-model="columnFilter.threshold"
                      label="Semantic Neighbors"
                      type="number"
                      variant="outlined"
                      density="comfortable"
                      hide-details="auto"
                    />
                  </v-col>
                </v-row>
              </v-col>
            </v-row>

            <v-divider class="my-4" />

            <v-row>
              <v-col cols="12">
                <div class="text-subtitle-1 mb-2">Percentile Predicate</div>
                <v-row>
                  <v-col cols="3">
                    <v-text-field
                      v-model="percentileFilter.percentile"
                      label="Percentile"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      variant="outlined"
                      density="comfortable"
                      hide-details="auto"
                    />
                  </v-col>
                  <v-col cols="3">
                    <v-select
                      v-model="percentileFilter.comparison"
                      :items="['gt', 'ge', 'lt', 'le']"
                      label="Comparison"
                      variant="outlined"
                      density="comfortable"
                      hide-details="auto"
                    />
                  </v-col>
                  <v-col cols="4">
                    <v-text-field
                      v-model="percentileFilter.value"
                      label="Value"
                      type="number"
                      variant="outlined"
                      density="comfortable"
                      hide-details="auto"
                    />
                  </v-col>
                </v-row>
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12">
                <div class="d-flex justify-end gap-2">
                  <v-btn
                    color="success"
                    :disabled="!isColumnFilterValid && !isPercentileFilterValid"
                    prepend-icon="mdi-plus"
                    class="mr-2"
                    @click="addFilters"
                  >
                    Add
                  </v-btn>
                  <v-btn
                    color="primary"
                    prepend-icon="mdi-magnify"
                    :disabled="!hasActiveFilters"
                    @click="searchData"
                  >
                    Run Query
                  </v-btn>
                </div>
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </v-expand-transition>
    </v-container>

    <!-- Settings Dialog -->
    <v-dialog v-model="showSettings" width="500">
      <v-card elevation="0">
        <v-card-title class="text-h5 mt-2"> Search Settings </v-card-title>

        <v-card-text>
          <v-select
            v-model="temp_fainder_mode"
            :items="fainder_modes"
            label="Fainder Mode"
            variant="outlined"
          />
          <v-switch
            v-model="temp_enable_highlighting"
            label="Enable Highlighting"
            color="primary"
          />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            color="error"
            variant="text"
            icon="mdi-close"
            @click="cancelSettings"
          />
          <v-btn
            color="success"
            variant="text"
            icon="mdi-check"
            @click="saveSettings"
          />
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-main>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, computed } from "vue";
import { useQueryParser, type SearchTerm } from "../composables/useQueryParser";

const props = defineProps({
  searchQuery: {
    type: String,
    default: "",
  },
  inline: {
    type: Boolean,
    default: false,
  },
  simpleBuilder: {
    type: Boolean,
    default: false,
  },
  lines: {
    type: Number,
    default: 1,
  },
});

const emit = defineEmits(["searchData"]);
const route = useRoute();
const temp_fainder_mode = ref(route.query.fainder_mode || "low_memory");
const temp_enable_highlighting = ref(
  route.query.enable_highlighting !== "false",
); // Default to true
const current_rows = ref(1);

interface BaseSearchTerm {
  type: "column" | "percentile" | "combined";
}

interface ColumnTerm extends BaseSearchTerm {
  type: "column";
  column: string;
  threshold: number;
}

interface PercentileTerm extends BaseSearchTerm {
  type: "percentile";
  percentile: number;
  comparison: "gt" | "ge" | "lt" | "le";
  value: number;
}

interface CombinedTerm extends BaseSearchTerm {
  type: "combined";
  column: string;
  threshold: number;
  percentile: number;
  comparison: "gt" | "ge" | "lt" | "le";
  value: number;
}

type SearchTerm = ColumnTerm | PercentileTerm | CombinedTerm;

// Replace the three separate arrays with one typed array
const searchTerms = ref<SearchTerm[]>([]);

const { fainder_mode, enable_highlighting } = useSearchState();

// Initialize fainder_mode if not already set
if (!fainder_mode.value) {
  fainder_mode.value = route.query.fainder_mode || "low_memory";
}
if (!enable_highlighting.value) {
  enable_highlighting.value = route.query.enable_highlighting !== "false"; // Default to true
}

const searchQuery = ref(props.searchQuery);
const syntaxError = ref("");
const highlightedQuery = ref("");
const highlightEnabled = useCookie("fainder_highlight_enabled", {
  default: () => true,
});
const isValid = ref(true);
const isSearchFocused = ref(false);

console.log("Initial fainder_mode:", fainder_mode?.value);

const showSettings = ref(false);
const fainder_modes = [
  { title: "Low Memory", value: "low_memory" },
  { title: "Full Precision", value: "full_precision" },
  { title: "Full Recall", value: "full_recall" },
  { title: "Exact Results", value: "exact" },
];

// Simple query builder state
const showSimpleBuilder = ref(false);

const columnFilter = ref({
  column: "",
  threshold: "",
});

const percentileFilter = ref({
  percentile: "",
  comparison: "",
  value: "",
});

// on change of highlightEnabled value, update syntax highlighting
watch(highlightEnabled, (value) => {
  // Clear error state when highlighting is disabled
  if (!value) {
    syntaxError.value = "";
    isValid.value = true;
  } else {
    // Force validation when highlighting is enabled
    isValid.value = validateSyntax(searchQuery.value);
  }
  // Update highlighting
  highlightSyntax(searchQuery.value);
});

const first_time = ref(true);

// Add a watch for showSimpleBuilder
watch(showSimpleBuilder, (isOpen) => {
  if (isOpen && first_time.value) {
    // Clear existing terms
    first_time.value = false;
    searchTerms.value = [];

    if (searchQuery.value) {
      parseExistingQuery(searchQuery.value);
      highlightSyntax(searchQuery.value);
    }
  }
});

const handleKeyDown = (event) => {
  if (!isSearchFocused.value) return;

  if (event.key === "Enter") {
    if (!event.shiftKey) {
      event.preventDefault();
      searchData();
    } else if (event.shiftKey) {
      if (current_rows.value < props.lines) {
        current_rows.value += 1; // on shift+enter, increase the number of rows
      }
    }
  }
};

const { parseQuery } = useQueryParser();

const parseExistingQuery = (query: string) => {
  if (!query) return;
  if (!props.simpleBuilder) {
    searchQuery.value = query;
    return;
  }

  const { terms, remainingQuery } = parseQuery(query);
  searchTerms.value = terms;
  searchQuery.value = remainingQuery;

  console.log("Parsed query results:", {
    searchTerms: searchTerms.value,
    remainingQuery: searchQuery.value,
  });
};

onMounted(() => {
  if (props.searchQuery) {
    searchQuery.value = props.searchQuery;
    highlightSyntax(searchQuery.value);
  }

  // Focus the textarea
  const textarea = document.querySelector(".search-input textarea");
  if (textarea) {
    textarea.focus();
  }
});

const textareaMaxHeight = computed(() => `${props.lines * 24 + 26}px`);

async function searchData() {
  if (
    (!searchQuery.value || searchQuery.value.trim() === "") &&
    searchTerms.value.length === 0
  ) {
    return;
  }

  // Combine search query with filter terms

  const terms = [];

  // Add column terms
  const columnQueryTerms = searchTerms.value
    .filter((term) => term.type === "column")
    .map(
      (term) =>
        `COLUMN(NAME(${(term as ColumnTerm).column};${(term as ColumnTerm).threshold}))`,
    );

  // Add percentile terms
  const percentileQueryTerms = searchTerms.value
    .filter((term) => term.type === "percentile")
    .map(
      (term) =>
        `COLUMN(PERCENTILE(${(term as PercentileTerm).percentile};${(term as PercentileTerm).comparison};${(term as PercentileTerm).value}))`,
    );

  // Add combined terms
  const combinedQueryTerms = searchTerms.value
    .filter((term) => term.type === "combined")
    .map(
      (term) =>
        `COLUMN(NAME(${(term as CombinedTerm).column};${(term as CombinedTerm).threshold}) AND PERCENTILE(${(term as CombinedTerm).percentile};${(term as CombinedTerm).comparison};${(term as CombinedTerm).value}))`,
    );
  if (columnQueryTerms.length) {
    terms.push(columnQueryTerms.join(" AND "));
  }

  if (percentileQueryTerms.length) {
    terms.push(percentileQueryTerms.join(" AND "));
  }

  if (combinedQueryTerms.length) {
    terms.push(combinedQueryTerms.join(" AND "));
  }
  // Combine filter terms
  const filterTerms = terms.join(" AND ");

  const filterQuery = filterTerms ? `${filterTerms}` : "";

  let query = searchQuery.value?.trim() || "";

  // Check if query is just plain text (no operators or functions)
  const isPlainText =
    !/(?:pp|percentile|kw|keyword|col|column)\s*\(|AND|OR|XOR|NOT|\(|\)/.test(
      query,
    );

  // Process plain text as keyword search
  if (isPlainText && query) {
    query = `KW(${query})`;
  }

  // Combine filter terms with query
  if (filterQuery) {
    query = query ? `${query} AND ${filterQuery}` : filterQuery;
  }

  const s_query = query;
  console.log("Search query:", s_query);
  console.log("Index type:", fainder_mode.value);
  console.log("Highlighting enabled:", enable_highlighting.value);
  emit("searchData", {
    query: s_query,
    fainder_mode: fainder_mode.value,
    enable_highlighting: enable_highlighting.value, // Add this line
  });
}

const validateSyntax = (value: string) => {
  if (!value || value.trim() === "" || !highlightEnabled.value) {
    syntaxError.value = "";
    isValid.value = true;
    return true;
  }

  try {
    // Reset state
    syntaxError.value = "";
    isValid.value = true;

    const query = value.trim();

    // If it's a simple keyword query (no special syntax), treat it as valid
    if (
      !query.includes("(") &&
      !query.includes(")") &&
      !/\b(AND|OR|XOR|NOT)\b/i.test(query)
    ) {
      return true;
    }

    // Check balanced parentheses
    const openParens = (value.match(/\(/g) || []).length;
    const closeParens = (value.match(/\)/g) || []).length;
    if (openParens !== closeParens) {
      isValid.value = false;
      syntaxError.value = "Unbalanced parentheses";
      return false;
    }

    // Extract and validate individual function calls
    const functionPattern =
      /(?:pp|percentile|kw|keyword|col|column|name)\s*\([^)]+\)/gi;
    const functions = value.match(functionPattern) || [];

    for (const func of functions) {
      const lowFunc = func.toLowerCase();
      if (lowFunc.startsWith("col") || lowFunc.startsWith("column")) {
        // Check if it contains name or percentile terms
        if (
          !/^(?:col|column)\s*\(\s*(?:name\s*\([^;]+;\s*\d+\)|pp\s*\([^)]+\))\s*\)$/i.test(
            func,
          )
        ) {
          // Check if it has invalid keyword inside
          if (/(?:kw|keyword)\s*\([^)]+\)/i.test(func)) {
            isValid.value = false;
            syntaxError.value =
              "Keywords not allowed inside column expressions";
            return false;
          }
        }
      } else if (lowFunc.startsWith("kw") || lowFunc.startsWith("keyword")) {
        if (!/^(?:kw|keyword)\s*\([^)]+\)$/i.test(func)) {
          isValid.value = false;
          syntaxError.value = "Invalid keyword syntax";
          return false;
        }
      } else if (lowFunc.startsWith("pp") || lowFunc.startsWith("percentile")) {
        if (
          !/^(?:pp|percentile)\s*\(\s*\d+(?:\.\d+)?\s*;\s*(?:ge|gt|le|lt)\s*;\s*\d+(?:\.\d+)?\s*\)$/i.test(
            func,
          )
        ) {
          isValid.value = false;
          syntaxError.value = "Invalid percentile syntax";
          return false;
        }
      } else if (lowFunc.startsWith("name")) {
        if (!/^name\s*\([^;]+;\s*\d+\)$/i.test(func)) {
          isValid.value = false;
          syntaxError.value = "Invalid name syntax";
          return false;
        }
      }
    }

    return true;
  } catch {
    isValid.value = false;
    syntaxError.value = "Invalid query syntax";
    return false;
  }
};

const highlightSyntax = (value: string) => {
  if (!value || !highlightEnabled.value) {
    highlightedQuery.value = value || "";
    return;
  }

  let highlighted = value;

  // Highlight all function names consistently
  highlighted = highlighted.replace(
    /\b(kw|keyword|name|pp|percentile|col|column)\s*\(/gi,
    '<span class="function">$1</span>(',
  );

  // Highlight content inside function calls
  highlighted = highlighted
    // Highlight comparison operators
    .replace(/;\s*(ge|gt|le|lt)\s*;/gi, ';<span class="comparison">$1</span>;')
    // Highlight numbers
    .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="number">$1</span>')
    // Highlight field names (text between parentheses and semicolon)
    .replace(/\(([^;)]+)(?=;)/g, '(<span class="field">$1</span>');

  // Highlight operators
  highlighted = highlighted
    .replace(/\bNOT\b/gi, '<span class="not-operator">NOT</span>')
    .replace(/\b(AND|OR|XOR)\b/gi, '<span class="operator">$1</span>');

  // Handle brackets
  let bracketLevel = 0;
  const nBracketColors = 4;

  highlighted = highlighted.replace(/[()]/g, (match) => {
    if (match === "(") {
      bracketLevel += 1;
      return `<span class="bracket-${(bracketLevel - 1) % nBracketColors}">(</span>`;
    } else {
      bracketLevel = Math.max(bracketLevel - 1, 0);
      return `<span class="bracket-${bracketLevel % nBracketColors}">)</span>`;
    }
  });

  highlightedQuery.value = highlighted;
};

// Remove a column term
const removeSearchTerm = (index: number) => {
  searchTerms.value.splice(index, 1);
};

const transferTerm = (term: SearchTerm, index: number) => {
  switch (term.type) {
    case "column":
      columnFilter.value = {
        column: term.column,
        threshold: term.threshold.toString(),
      };
      break;
    case "percentile":
      percentileFilter.value = {
        percentile: term.percentile.toString(),
        comparison: term.comparison,
        value: term.value.toString(),
      };
      break;
    case "combined":
      columnFilter.value = {
        column: term.column,
        threshold: term.threshold.toString(),
      };
      percentileFilter.value = {
        percentile: term.percentile.toString(),
        comparison: term.comparison,
        value: term.value.toString(),
      };
      break;
  }
  removeSearchTerm(index);
};

const isColumnFilterValid = computed(() => {
  const f = columnFilter.value;
  return f.column?.trim() && f.threshold !== "" && !isNaN(f.threshold);
});

const isPercentileFilterValid = computed(() => {
  const f = percentileFilter.value;
  return (
    f.percentile !== "" &&
    parseFloat(f.percentile) >= 0 &&
    parseFloat(f.percentile) <= 1 &&
    f.comparison &&
    f.value !== "" &&
    !isNaN(f.value)
  );
});

const addFilters = () => {
  if (isColumnFilterValid.value && !isPercentileFilterValid.value) {
    searchTerms.value.push({
      type: "column",
      column: columnFilter.value.column,
      threshold: parseFloat(columnFilter.value.threshold),
    });
    columnFilter.value = { column: "", threshold: "" };
  } else if (isPercentileFilterValid.value && !isColumnFilterValid.value) {
    searchTerms.value.push({
      type: "percentile",
      percentile: parseFloat(percentileFilter.value.percentile),
      comparison: percentileFilter.value.comparison as
        | "gt"
        | "ge"
        | "lt"
        | "le",
      value: parseFloat(percentileFilter.value.value),
    });
    percentileFilter.value = { percentile: "", comparison: "", value: "" };
  } else if (isColumnFilterValid.value && isPercentileFilterValid.value) {
    searchTerms.value.push({
      type: "combined",
      column: columnFilter.value.column,
      threshold: parseFloat(columnFilter.value.threshold),
      percentile: parseFloat(percentileFilter.value.percentile),
      comparison: percentileFilter.value.comparison as
        | "gt"
        | "ge"
        | "lt"
        | "le",
      value: parseFloat(percentileFilter.value.value),
    });
    columnFilter.value = { column: "", threshold: "" };
    percentileFilter.value = { percentile: "", comparison: "", value: "" };
  }
};

const hasActiveFilters = computed(() => {
  return (
    searchTerms.value.length > 0 ||
    (searchQuery.value && searchQuery.value.trim() !== "")
  );
});

function cancelSettings() {
  showSettings.value = false;
}

function saveSettings() {
  showSettings.value = false;
  fainder_mode.value = temp_fainder_mode.value;
  enable_highlighting.value = temp_enable_highlighting.value;
  console.log("New fainder_mode:", fainder_mode.value);
  console.log("New highlighting enabled:", enable_highlighting.value);
  // update route
  const route = useRoute();
  navigateTo({
    path: route.path,
    query: {
      ...route.query,
      fainder_mode: temp_fainder_mode.value,
      enable_highlighting: temp_enable_highlighting.value,
    },
  });
}
</script>

<style scoped>
.search-main {
  background-color: transparent !important;
}

.inline-layout {
  align-items: center;
}

.search-btn {
  height: 48px;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: none;
  border-radius: 8px;
  display: flex;
  align-items: center;
}

.settings-btn {
  height: 48px;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: none;
  border-radius: 8px;
  display: flex;
  align-items: center;
}

.input-wrapper {
  position: relative;
  width: 100%;
}

.search-input {
  margin-bottom: 4px;
}

.search-input :deep(textarea) {
  position: relative;
  color: transparent !important;
  background: transparent !important;
  caret-color: rgb(
    var(--v-theme-on-surface)
  ); /* Updated: theme-aware caret color */
  z-index: 2;
  white-space: pre;
  font-family: "Roboto Mono", monospace;
  font-size: 16px;
  letter-spacing: normal;
  line-height: normal;
  padding: 8px 16px;
  padding-top: 15px;
  min-height: 50px;
  resize: none;
  overflow-y: auto;
}

/* Adjust max-height based on lines prop when in inline mode */
.inline-layout .search-input :deep(textarea) {
  max-height: v-bind(textareaMaxHeight);
  overflow: auto;
}

.syntax-highlight {
  position: absolute;
  padding-top: 15px;
  top: 0px;
  left: 16px;
  right: 48px;
  pointer-events: none;
  font-family: "Roboto Mono", monospace;
  font-size: 16px;
  z-index: 1;
  color: rgba(var(--v-theme-on-surface), 0.87);
  mix-blend-mode: normal;
  white-space: pre;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: normal;
  line-height: normal;
}

.error-message {
  color: rgb(var(--v-theme-error));
  font-size: 12px;
  margin-top: 4px;
  min-height: 20px;
  padding-left: 16px;
}

/* Remove background colors from syntax highlighting */
.syntax-highlight :deep(.operator) {
  color: #5c6bc0; /* Indigo */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.not-operator) {
  color: #ff5252; /* Red accent */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.number) {
  color: #00bcd4; /* Cyan */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.field) {
  color: #66bb6a; /* Light green */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.function) {
  color: #8e24aa; /* Purple */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.comparison) {
  color: #fb8c00; /* Orange */
  background-color: transparent;
  padding: 0;
}

/* Add bracket pair colors */
.syntax-highlight :deep(.bracket-0) {
  color: #e91e63; /* Pink */
  background-color: transparent;
}

.syntax-highlight :deep(.bracket-1) {
  color: #2196f3; /* Blue */
  background-color: transparent;
}

.syntax-highlight :deep(.bracket-2) {
  color: #4caf50; /* Green */
  background-color: transparent;
}

.syntax-highlight :deep(.bracket-3) {
  color: #ffc107; /* Amber */
  background-color: transparent;
}

.query-builder {
  background-color: rgba(var(--v-theme-surface), 0.8);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.gap-2 {
  gap: 8px;
}

.builder-header {
  display: flex;
  align-items: center;
  color: rgba(var(--v-theme-on-surface), 0.87);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.builder-header .v-icon {
  opacity: 0.7;
}
</style>
