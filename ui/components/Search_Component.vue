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
              @update:model-value="highlightSyntax"
              hide-details="true"
              rows="1"
              class="search-input"
              append-inner-icon="mdi-magnify"
              auto-grow
            />
            <div class="syntax-highlight" v-html="highlightedQuery"></div>
            <div v-if="syntaxError" class="error-message">{{ syntaxError }}</div>
          </div>
        </v-col>
        <v-col cols="1">
          <v-btn icon="mdi-cog" @click="showSettings = true" variant="text">
          </v-btn>
        </v-col>
      </v-row>

      <!-- Simple Query Builder Toggle Button -->
      <v-row v-if="simpleBuilder" class="mt-4">
        <v-col cols="12">
          <v-btn
            v-if="!showSimpleBuilder"
            block
            variant="outlined"
            @click="showSimpleBuilder = true"
            prepend-icon="mdi-plus"
            color="primary"
          >
            Add Column Filters
          </v-btn>
        </v-col>
      </v-row>

      <!-- Simple Query Builder -->
      <v-expand-transition>
        <v-row v-if="simpleBuilder && showSimpleBuilder" class="query-builder mt-4">
          <v-col cols="12">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="builder-header">
                <v-icon icon="mdi-database-search" class="mr-2" />
                <span class="text-h6">Query Builder</span>
              </div>
              <v-btn
                variant="text"
                icon="mdi-close"
                size="small"
                @click="showSimpleBuilder = false"
              />
            </div>

            <!-- Combined filters list -->
            <v-chip-group class="mb-4">
              <v-chip
                v-for="(term, index) in columnTerms"
                :key="`col-${index}`"
                closable
                @click:close="removeColumnTerm(index)"
                color="primary"
              >
                col({{ term.column }};{{ term.threshold }})
              </v-chip>
              <v-chip
                v-for="(term, index) in percentileTerms"
                :key="`percentile-${index}`"
                closable
                @click:close="removePercentileTerm(index)"
                color="indigo"
              >
                pp({{ term.percentile }};{{ term.comparison }};{{ term.value }})
              </v-chip>
            </v-chip-group>

            <!-- Split into separate rows -->
            <v-row>
              <v-col cols="12">
                <div class="text-subtitle-1 mb-2">Column Filter</div>
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
                      label="Threshold"
                      type="number"
                      variant="outlined"
                      density="comfortable"
                      hide-details="auto"
                    />
                  </v-col>
                  <v-col cols="2" class="d-flex align-center">
                    <v-btn
                      color="primary"
                      @click="addColumnFilter"
                      :disabled="!isColumnFilterValid"
                      prepend-icon="mdi-plus"
                    >
                      Add
                    </v-btn>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>

            <v-divider class="my-4"></v-divider>

            <v-row>
              <v-col cols="12">
                <div class="text-subtitle-1 mb-2">Percentile Filter</div>
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
                  <v-col cols="2" class="d-flex align-center">
                    <v-btn
                      color="indigo"
                      @click="addPercentileFilter"
                      :disabled="!isPercentileFilterValid"
                      prepend-icon="mdi-plus"
                    >
                      Add
                    </v-btn>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12">
                <div class="d-flex justify-end">
                  <v-btn
                    color="success"
                    @click="addBothFilters"
                    :disabled="!isColumnFilterValid || !isPercentileFilterValid"
                    prepend-icon="mdi-plus-circle-multiple"
                    class="mr-2"
                  >
                    Add Both
                  </v-btn>
                </div>
              </v-col>
            </v-row>

          </v-col>
        </v-row>
      </v-expand-transition>

      <!-- Query Builder Tools -->
      <v-row v-if="queryBuilder" class="query-builder mt-4">
        <v-col cols="12">
          <div class="builder-header mb-2">
            <v-icon icon="mdi-puzzle" class="mr-2" />
            <span class="text-h6">Add Operator</span>
          </div>
          <div class="d-flex flex-wrap gap-2">
            <v-chip
              v-for="op in operators"
              :key="op.text"
              :color="op.color"
              class="mr-2 mb-2"
              @click="insertOperator(op.text)"
            >
              {{ op.text }}
            </v-chip>
            <v-chip
              v-for="func in functions"
              :key="func.name"
              :color="func.color"
              class="mr-2 mb-2"
              @click="openFunctionDialog(func.type)"
            >
              {{ func.name }}
            </v-chip>
          </div>
        </v-col>
      </v-row>
    </v-container>

    <!-- Function Dialogs -->
    <v-dialog v-model="showFunctionDialog" max-width="500px">
      <v-card>
        <v-card-title>{{
          currentFunction?.name || "Build Function"
        }}</v-card-title>
        <v-card-text>
          <!-- Percentile Function Builder -->
          <div v-if="currentFunction?.type === 'percentile'">
            <v-text-field
              v-model="functionParams.percentile"
              label="Percentile"
              type="number"
              min="0"
              max="1"
              step="0.01"
              :rules="[
                (v) => !!v || 'Percentile is required',
                (v) =>
                  (v >= 0 && v <= 1) || 'Percentile must be between 0 and 1',
              ]"
              hide-details="auto"
            />
            <v-select
              v-model="functionParams.comparison"
              :items="['gt', 'ge', 'lt', 'le']"
              label="Comparison"
              :rules="[(v) => !!v || 'Comparison operator is required']"
              hide-details="auto"
              class="mt-4"
            />
            <v-text-field
              v-model="functionParams.value"
              label="Value"
              type="number"
              :rules="[(v) => !!v || 'Value is required']"
              hide-details="auto"
              class="mt-4"
            />
          </div>
          <!-- Keyword Function Builder -->
          <div v-if="currentFunction?.type === 'keyword'">
            <v-text-field
              v-model="functionParams.keyword"
              label="Search Terms"
              :rules="[(v) => !!v || 'Search terms are required']"
              hide-details="auto"
            />
          </div>
          <!-- Column Function Builder -->
          <div v-if="currentFunction?.type === 'column'">
            <v-text-field
              v-model="functionParams.column"
              label="Column Name"
              :rules="[(v) => !!v || 'Column name is required']"
              hide-details="auto"
            />
            <v-text-field
              v-model="functionParams.threshold"
              label="Threshold"
              type="number"
              :rules="[(v) => !!v || 'Threshold is required']"
              hide-details="auto"
              class="mt-4"
            />
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn
            color="error"
            variant="text"
            @click="showFunctionDialog = false"
            >Cancel</v-btn
          >
          <v-btn
            color="primary"
            variant="text"
            @click="validateAndInsert"
            :disabled="!isFormValid"
          >
            Insert
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Settings Dialog -->
    <v-dialog v-model="showSettings" width="500">
      <v-card>
        <v-card-title class="text-h5"> Search Settings </v-card-title>

        <v-card-text>
          <v-select
            v-model="temp_fainder_mode"
            :items="fainder_modes"
            label="Fainder Mode"
            variant="outlined"
          />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            color="error"
            variant="text"
            @click="cancelSettings"
            icon="mdi-close"
          />
          <v-btn
            color="primary"
            variant="text"
            @click="saveSettings"
            icon="mdi-content-save-all"
          />
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-main>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch, nextTick, computed } from "vue";

const props = defineProps({
  searchQuery: String,
  inline: {
    type: Boolean,
    default: false,
  },
  queryBuilder: {
    type: Boolean,
    default: true,
  },
  simpleBuilder: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["searchData"]);
const route = useRoute();
const temp_fainder_mode = ref(route.query.fainder_mode || "low_memory");

const { fainder_mode } = useSearchState();
// Initialize fainder_mode if not already set
if (!fainder_mode.value) {
  fainder_mode.value = route.query.fainder_mode || "low_memory";
}

const searchQuery = ref(props.searchQuery);
const syntaxError = ref("");
const highlightedQuery = ref("");
const highlightEnabled = useCookie("highlight-enabled");
const isValid = ref(true);

console.log("Initial fainder_mode:", fainder_mode?.value);

const showSettings = ref(false);
const fainder_modes = [
  { title: "Low Memory Mode", value: "low_memory" },
  { title: "Full Precision Mode", value: "full_precision" },
  { title: "Full Recall Mode", value: "full_recall" },
  { title: "Exact Mode", value: "exact" },
];

// Query builder state
const showFunctionDialog = ref(false);
const currentFunction = ref(null);
const functionParams = ref({ value: {} }); // Initialize with nested value object


// Simple query builder state
const showSimpleBuilder = ref(false);

const columnFilter = ref({
  column: '',
  threshold: ''
});

const percentileFilter = ref({
  percentile: '',
  comparison: '',
  value: ''
});


const operators = [
  { text: "AND", color: "primary" },
  { text: "OR", color: "secondary" },
  { text: "XOR", color: "warning" },
  { text: "NOT", color: "error" },
];

const functions = [
  { type: "percentile", name: "Percentile", color: "indigo" },
  { type: "keyword", name: "Keyword", color: "teal" },
  { type: "column", name: "Column", color: "deep-purple" },
];

// Insert operator at cursor position or at end
const insertOperator = (operator) => {
  const input = document.querySelector(".search-input input");
  const cursorPos = input.selectionStart;
  const currentValue = searchQuery.value || "";

  const beforeCursor = currentValue.substring(0, cursorPos);
  const afterCursor = currentValue.substring(cursorPos);

  // Add space before operator if there's text before and it doesn't end with space
  const needsSpaceBefore =
    beforeCursor.length > 0 && !beforeCursor.endsWith(" ");
  // Add space after operator if there's text after and it doesn't start with space
  const needsSpaceAfter =
    afterCursor.length > 0 && !afterCursor.startsWith(" ");

  const spacedOperator = `${needsSpaceBefore ? " " : ""}${operator}${
    needsSpaceAfter ? " " : ""
  }`;
  searchQuery.value = `${beforeCursor}${spacedOperator}${afterCursor}`;
  highlightSyntax(searchQuery.value);

  // Restore focus and move cursor after inserted operator and space
  nextTick(() => {
    input.focus();
    const newPos = cursorPos + spacedOperator.length;
    input.setSelectionRange(newPos, newPos);
  });
};

// Open function builder dialog
const openFunctionDialog = (type) => {
  currentFunction.value = functions.find((f) => f.type === type);
  functionParams.value = { value: {} }; // Reset with proper structure
  showFunctionDialog.value = true;
};

// Build and insert function based on type
const validateAndInsert = () => {
  if (!isFormValid.value) return;

  let functionText = "";
  switch (currentFunction.value.type) {
    case "percentile":
      functionText = `pp(${parseFloat(functionParams.value.percentile)};${
        functionParams.value.comparison
      };${parseFloat(functionParams.value.value)})`;
      break;
    case "keyword":
      functionText = `kw(${functionParams.value.keyword.trim()})`;
      break;
    case "column":
      functionText = `col(${functionParams.value.column.trim()};${parseFloat(
        functionParams.value.threshold
      )})`;
      break;
  }

  const input = document.querySelector(".search-input input");
  const cursorPos = input.selectionStart;
  const currentValue = searchQuery.value || "";

  const beforeCursor = currentValue.substring(0, cursorPos);
  const afterCursor = currentValue.substring(cursorPos);

  searchQuery.value = `${beforeCursor}${functionText}${afterCursor}`;
  highlightSyntax(searchQuery.value);

  showFunctionDialog.value = false;

  // Restore focus
  nextTick(() => {
    input.focus();
    const newPos = cursorPos + functionText.length;
    input.setSelectionRange(newPos, newPos);
  });
};


const isFormValid = computed(() => {
  if (!currentFunction.value || !functionParams.value) return false;

  switch (currentFunction.value.type) {
    case "percentile":
      return (
        !!functionParams.value.percentile &&
        parseFloat(functionParams.value.percentile) >= 0 &&
        parseFloat(functionParams.value.percentile) <= 1 &&
        !!functionParams.value.comparison &&
        !!functionParams.value.value
      );
    case "keyword":
      return (
        !!functionParams.value.keyword &&
        functionParams.value.keyword.trim() !== ""
      );
    case "column":
      return (
        !!functionParams.value.column &&
        functionParams.value.column.trim() !== "" &&
        !!functionParams.value.threshold
      );
    default:
      return false;
  }
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

const handleKeyDown = (event) => {
  if (event.key === "Enter") {
    searchData();
  }
};

onMounted(() => {
  window.addEventListener("keydown", handleKeyDown);
  // Initialize syntax highlighting if there's an initial search query
  if (props.searchQuery) {
    highlightSyntax(props.searchQuery);
  }
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
});

async function searchData() {
  if ((!searchQuery.value || searchQuery.value.trim() === "" )
  && columnTerms.value.length === 0 && percentileTerms.value.length === 0) {
    return;
  }

  // Combine search query with filter terms

  const terms = [];

  // Add column terms
  const columnQueryTerms = columnTerms.value.map(term =>
    `col(${term.column};${term.threshold})`
  );

  // Add percentile terms
  const percentileQueryTerms = percentileTerms.value.map(term =>
    `pp(${term.percentile};${term.comparison};${term.value})`
  );
  if (columnQueryTerms.length) {
    terms.push(columnQueryTerms.join(' AND '));
  }

  if (percentileQueryTerms.length) {
    terms.push(percentileQueryTerms.join(' AND '));
  }
  // Combine filter terms
  const filterQuery = terms.join(' AND ');


  let query = searchQuery.value?.trim() || '';

  // Check if query is just plain text (no operators or functions)
  const isPlainText = !/(?:pp|percentile|kw|keyword|col|column)\s*\(|AND|OR|XOR|NOT|\(|\)/.test(query);

  // Process plain text as keyword search
  if (isPlainText && query) {
    query = `kw(${query})`;
  }

  // Combine filter terms with query
  if (filterQuery) {
    query = query ? `${query} AND ${filterQuery}` : filterQuery;
  }


  console.log("Search query:", query);
  console.log("Index type:", fainder_mode);
  emit("searchData", {
    query: query,
    fainder_mode: fainder_mode.value,
  });
}

const validateSyntax = (value) => {
  if (!value || value.trim() === "" || !highlightEnabled.value) {
    syntaxError.value = "";
    isValid.value = true;
    return true;
  }

  // Reset state
  syntaxError.value = "";
  isValid.value = true;

  try {
    const query = value.trim();

    // If it's a simple keyword query (no special syntax), treat it as valid
    if (
      !query.includes("(") &&
      !query.includes(")") &&
      !/\b(AND|OR|XOR|NOT)\b/i.test(query)
    ) {
      return true;
    }

    // Check if it's a simple keyword function
    if (/^(kw|keyword)\s*\([^)]+\)$/i.test(query)) {
      return true;
    }

    // Rest of validation for complex queries
    const functionPattern =
      /(?:pp|percentile|kw|keyword|col|column)\s*\([^)]+\)/gi;
    const operatorPattern = /\b(AND|OR|XOR|NOT)\b/gi;
    const parenthesesPattern = /[()]/g;

    // For complex queries, check each component
    if (
      !functionPattern.test(value) &&
      !operatorPattern.test(value) &&
      !parenthesesPattern.test(value)
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

    // Validate individual function patterns
    const functions = value.match(functionPattern) || [];
    for (const func of functions) {
      if (
        !/^(pp|percentile)\s*\(\s*\d+(\.\d+)?\s*;\s*(ge|gt|le|lt)\s*;\s*\d+(\.\d+)?\s*\)$/i.test(
          func
        ) &&
        !/^(kw|keyword)\s*\([^)]+\)$/i.test(func) &&
        !/^(col|column)\s*\([^;]+;\s*\d+\)$/i.test(func)
      ) {
        isValid.value = false;
        syntaxError.value = "Invalid function syntax";
        return false;
      }
    }

    return true;
  } catch (e) {
    isValid.value = false;
    syntaxError.value = "Invalid query syntax";
    return false;
  }
};

const highlightSyntax = (value) => {
  if (!value) {
    highlightedQuery.value = "";
    return;
  }
  if (!highlightEnabled.value) {
    highlightedQuery.value = value;
    return;
  }

  let highlighted = value;

  // Use more specific regex patterns with lookahead/lookbehind
  highlighted = highlighted
    // Functions - match the entire function call
    .replace(
      /(?:pp|percentile|kw|keyword|col|column)\s*\([^)]+\)/gi,
      (match) => {
        return (
          match
            // Highlight function name
            .replace(
              /(pp|percentile|kw|keyword|col|column)\s*(?=\()/i,
              '<span class="function">$1</span>'
            )
            // Highlight numbers
            .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="number">$1</span>')
            // Highlight comparisons
            .replace(
              /\b(ge|gt|le|lt)\b/gi,
              '<span class="comparison">$1</span>'
            )
            // Highlight field names
            .replace(
              /;\s*([a-zA-Z0-9_]+)\s*(?=\))/g,
              ';<span class="field">$1</span>'
            )
        );
      }
    )
    // Highlight operators - use word boundaries to avoid partial matches
    .replace(/\bNOT\b/gi, '<span class="not-operator">NOT</span>')
    .replace(/\b(AND|OR|XOR)\b/gi, '<span class="operator">$1</span>');

  // Handle brackets
  let bracketLevel = 0;
  const maxBracketLevels = 4;

  // Process opening brackets
  highlighted = highlighted.replace(/\(/g, () => {
    const bracket = `<span class="bracket-${bracketLevel}">&#40;</span>`;
    bracketLevel = (bracketLevel + 1) % maxBracketLevels;
    return bracket;
  });

  // Reset bracket level for closing brackets
  bracketLevel = 0;

  // Process closing brackets
  highlighted = highlighted.replace(/\)/g, () => {
    const bracket = `<span class="bracket-${bracketLevel}">&#41;</span>`;
    bracketLevel = (bracketLevel + 1) % maxBracketLevels;
    return bracket;
  });

  highlightedQuery.value = highlighted;
};

// Add these new refs for column terms management
const columnTerms = ref([]);
const percentileTerms = ref([]);

// Remove a column term
const removeColumnTerm = (index) => {
  columnTerms.value.splice(index, 1);
};

// Remove percentile term
const removePercentileTerm = (index) => {
  percentileTerms.value.splice(index, 1);
};

// Separate validation for each filter type
const isColumnFilterValid = computed(() => {
  const f = columnFilter.value;
  return f.column?.trim() && f.threshold !== '' && !isNaN(f.threshold);
});

const isPercentileFilterValid = computed(() => {
  const f = percentileFilter.value;
  return f.percentile !== '' &&
         parseFloat(f.percentile) >= 0 &&
         parseFloat(f.percentile) <= 1 &&
         f.comparison &&
         f.value !== '' &&
         !isNaN(f.value);
});

// Separate add functions for each filter type
const addColumnFilter = () => {
  if (!isColumnFilterValid.value) return;

  columnTerms.value.push({
    column: columnFilter.value.column,
    threshold: parseFloat(columnFilter.value.threshold)
  });

  // Reset form
  columnFilter.value = {
    column: '',
    threshold: ''
  };
};

const addPercentileFilter = () => {
  if (!isPercentileFilterValid.value) return;

  percentileTerms.value.push({
    percentile: parseFloat(percentileFilter.value.percentile),
    comparison: percentileFilter.value.comparison,
    value: parseFloat(percentileFilter.value.value)
  });

  // Reset form
  percentileFilter.value = {
    percentile: '',
    comparison: '',
    value: ''
  };
};

const addBothFilters = () => {
  if (!isColumnFilterValid.value || !isPercentileFilterValid.value) return;

  // Add column filter
  columnTerms.value.push({
    column: columnFilter.value.column,
    threshold: parseFloat(columnFilter.value.threshold)
  });

  // Add percentile filter
  percentileTerms.value.push({
    percentile: parseFloat(percentileFilter.value.percentile),
    comparison: percentileFilter.value.comparison,
    value: parseFloat(percentileFilter.value.value)
  });

  // Reset both forms
  columnFilter.value = {
    column: '',
    threshold: ''
  };

  percentileFilter.value = {
    percentile: '',
    comparison: '',
    value: ''
  };
};

function cancelSettings() {
  showSettings.value = false;
}

function saveSettings() {
  showSettings.value = false;
  fainder_mode.value = temp_fainder_mode.value;
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
  caret-color: black;
  z-index: 2;
  white-space: pre;
  font-family: 'Roboto Mono', monospace;
  font-size: 16px;
  letter-spacing: normal;
  line-height: normal;
  padding: 8px 16px;
  min-height: 45px;
  resize: none;
}

.syntax-highlight {
  position: absolute;
  top: 8px;
  left: 16px;
  right: 48px;
  pointer-events: none;
  font-family: 'Roboto Mono', monospace;
  font-size: 16px;
  z-index: 1;
  color: rgba(0, 0, 0, 0.87);
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
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  margin-bottom: 12px;
}

.builder-header .v-icon {
  opacity: 0.7;
}
</style>
