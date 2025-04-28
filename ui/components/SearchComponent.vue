# Search page for datasets search by precentile predicates and search by key
words # The search page will contain multiple search bars

<template>
  <v-main class="search-main pa-3">
    <v-container class="pa-2">
      <v-row class="inline-layout">
        <v-col cols="10">
          <div class="input-wrapper">
            <code-input
              language="DQL"
              template="syntax-highlighted"
              class="search-input"
              placeholder="Search for datasets"
              :value="searchQuery"
              :style="{ height: heightCodeInput }"
              @input="(e: any) => (searchQuery = e.target.value)"
              @keydown="handleKeyDown"
            />

            <div v-if="syntaxError" class="error-message">
              {{ syntaxError }}
            </div>
          </div>
        </v-col>
        <v-col cols="1">
          <v-btn
            icon="mdi-magnify"
            variant="text"
            elevation="0"
            density="compact"
            class="ml-2"
            @click="searchData"
          />
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
                v-for="(term, termIndex) in searchTerms"
                :key="termIndex"
                closable
                color="primary"
                @click:close="removeSearchTerm(termIndex)"
                @click="transferTerm(term.predicates, termIndex)"
              >
                COLUMN(
                <template
                  v-for="(predicate, predicateIndex) in term.predicates"
                  :key="predicateIndex"
                >
                  <template v-if="predicateIndex > 0"> AND </template>
                  <template v-if="predicate.type === 'name'">
                    NAME({{ predicate.column }};{{ predicate.threshold }})
                  </template>
                  <template v-else>
                    PERCENTILE({{ predicate.percentile }};{{
                      predicate.comparison
                    }};{{ predicate.value }})
                  </template>
                </template>
                )
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
import parseQuery from "~/utils/queryParser";

// Declare codeInput as a global variable from the loaded script
declare global {
  const codeInput: {
    Template: new (
      highlightFn: (element: HTMLElement) => string,
      preStyled?: boolean,
      setLanguageClass?: boolean,
      passSelf?: boolean,
      plugins?: unknown[],
    ) => unknown;
    registerTemplate: (name: string, template: unknown) => void;
  };
}

function highlightSyntax(value: string) {
  if (enable_highlighting.value === false) {
    return value;
  }
  //console.log(value);

  let highlighted = String(value);
  // console.log(value);

  // Highlight strings
  highlighted = highlighted.replace(
    /(['"])(.*?)\1/g,
    '<span class="string">$&</span>',
  );

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
    // Don't highlight field names if they're already highlighted as strings
    .replace(/\(([^;']+)(?=;)/g, '(<span class="field">$1</span>');

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

  // console.log("highlighted: ", String(highlighted));

  return highlighted;
}

function registerTemplate() {
  // codeInput.registerTemplate("syntax-highlighted", codeInput.templates.prism(hljs, [] /* Array of plugins (see below) */));
  codeInput.registerTemplate(
    "syntax-highlighted",
    new codeInput.Template(
      function (result_element: HTMLElement) {
        /* Highlight function - with `pre code` code element */
        /* Highlight code in result_element - code is already escaped so it doesn't become HTML */
        result_element.innerHTML = highlightSyntax(result_element.innerHTML);
        return result_element.innerHTML;
      },

      true /* Optional - Is the `pre` element styled as well as the `code` element?
       * Changing this to false uses the code element as the scrollable one rather
       * than the pre element */,

      true /* Optional - This is used for editing code - setting this to true sets the `code`
       * element's class to `language-<the code-input's lang attribute>` */,

      false /* Optional - Setting this to true passes the `<code-input>` element as a second
       * argument to the highlight function to be used for getting data- attribute values
       * and using the DOM for the code-input */,

      [], // Array of plugins (see below)
    ),
  );
}

registerTemplate();

const heightCodeInput = computed(() => {
  return `${visable_rows.value * 48}px`;
});

const props = defineProps({
  searchQuery: {
    type: String,
    default: " ",
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
  route.query.enable_highlighting === "true",
); // Default to false
const visable_rows = ref(props.lines);
const number_of_rows = ref(props.lines);

const searchTerms = ref<Term[]>([]);

const { fainder_mode, enable_highlighting } = useSearchState();

// Initialize fainder_mode if not already set
if (!fainder_mode.value) {
  fainder_mode.value = String(route.query.fainder_mode) || "low_memory";
}
if (enable_highlighting.value === undefined) {
  enable_highlighting.value = route.query.enable_highlighting === "true"; // Default to false
}

const searchQuery = ref(props.searchQuery);
const syntaxError = computed(() => {
  // console.log(searchQuery.value);
  if (
    !searchQuery.value ||
    searchQuery.value.trim() === "" ||
    !highlightEnabled.value
  ) {
    return "";
  }
  return validateSyntax(searchQuery.value);
});
const highlightEnabled = useCookie("fainder_highlight_enabled", {
  default: () => false,
});
const isValid = ref(true);

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

// on change of highlightEnabled value, update isValid
watch(highlightEnabled, (value) => {
  if (!value) {
    isValid.value = true;
  } else {
    isValid.value = !syntaxError.value;
  }
});

// Add a watch for showSimpleBuilder
watch(showSimpleBuilder, (isOpen) => {
  if (isOpen) {
    // Clear existing terms
    searchTerms.value = [];

    if (searchQuery.value) {
      parseExistingQuery(searchQuery.value);
    }
  }
});

interface KeyboardEvent {
  key: string;
  shiftKey: boolean;
  preventDefault: () => void;
}

const handleKeyDown = (
  event: KeyboardEvent & { target: HTMLInputElement },
): void => {
  // Update searchQuery immediately
  searchQuery.value = event.target.value;
  //console.log("Key pressed:", event.key);

  if (event.key === "Enter") {
    if (!event.shiftKey) {
      event.preventDefault();
      console.log("Enter key pressed searching", searchQuery.value);
      searchData();
    } else if (event.shiftKey) {
      if (!props.inline) {
        console.log("Shift+Enter key pressed increasing rows");
        visable_rows.value += 1; // on shift+enter, increase the number of rows
      }
      number_of_rows.value += 1;
    }
  } else if (event.key === "Backspace") {
    // Check if cursor is at the end of the last line and the line is empty
    const cursorPos = event.target.selectionStart;
    const lastLineStart = event.target.value.lastIndexOf("\n") + 1;
    const isLastLineEmpty =
      event.target.value.substring(lastLineStart).trim() === "";
    const isAtEnd = cursorPos === event.target.value.length;

    if (isLastLineEmpty && isAtEnd && visable_rows.value > 1) {
      if (!props.inline) {
        visable_rows.value -= 1;
      }
      number_of_rows.value -= 1;
      console.log("Backspace key pressed decreasing rows");
    }
  }
};

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
  }

  // Focus the textarea
  const textarea = document.querySelector(
    ".search-input textarea",
  ) as HTMLTextAreaElement;
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
    console.log("No search terms or query provided.");
    return;
  }

  // Convert search terms to string using utility function
  const filterTerms =
    searchTerms.value.length > 0 ? termsToString(searchTerms.value) : "";

  let query = searchQuery.value?.trim() || "";

  // Check if query is just plain text (no operators or functions)
  const isPlainText =
    !/(?:pp|percentile|kw|keyword|col|column)\s*\(|AND|OR|XOR|NOT|\(|\)/.test(
      query,
    );

  // Process plain text as keyword search
  if (isPlainText && query) {
    query = `KW('${query}')`;
  }

  // Combine filter terms with query
  if (filterTerms) {
    query = query ? `${query} AND ${filterTerms}` : filterTerms;
  }

  const s_query = query;
  console.log("Search query:", s_query);
  console.log("Index type:", fainder_mode.value);
  console.log("Highlighting enabled:", enable_highlighting.value);
  emit("searchData", {
    query: s_query,
    fainder_mode: fainder_mode.value,
    enable_highlighting: enable_highlighting.value,
  });
}

const validateSyntax = (value: string): string => {
  try {
    const query = value.trim();

    // If it's a simple keyword query (no special syntax), treat it as valid
    if (
      !query.includes("(") &&
      !query.includes(")") &&
      !/\b(AND|OR|XOR|NOT)\b/i.test(query)
    ) {
      return "";
    }

    // Check balanced parentheses
    const openParens = (value.match(/\(/g) || []).length;
    const closeParens = (value.match(/\)/g) || []).length;
    if (openParens !== closeParens) {
      return "Unbalanced parentheses";
    }

    // Extract and validate individual function calls
    const functionPattern =
      /(?:pp|percentile|kw|keyword|col|column|name)\s*\([^)]+\)/gi;
    const functions = value.match(functionPattern) || [];

    for (const func of functions) {
      const lowFunc = func.toLowerCase();
      if (lowFunc.startsWith("col") || lowFunc.startsWith("column")) {
        if (
          !/^(?:col|column)\s*\(\s*(?:name\s*\([^;]+;\s*\d+\)|pp\s*\([^)]+\))\s*\)$/i.test(
            func,
          )
        ) {
          if (/(?:kw|keyword)\s*\([^)]+\)/i.test(func)) {
            return "Keywords not allowed inside column expressions";
          }
        }
      } else if (lowFunc.startsWith("kw") || lowFunc.startsWith("keyword")) {
        if (!/^(?:kw|keyword)\s*\([^)]+\)$/i.test(func)) {
          return "Invalid keyword syntax";
        }
      } else if (lowFunc.startsWith("pp") || lowFunc.startsWith("percentile")) {
        if (
          !/^(?:pp|percentile)\s*\(\s*\d+(?:\.\d+)?\s*;\s*(?:ge|gt|le|lt)\s*;\s*\d+(?:\.\d+)?\s*\)$/i.test(
            func,
          )
        ) {
          return "Invalid percentile syntax";
        }
      } else if (lowFunc.startsWith("name")) {
        if (!/^name\s*\([^;]+;\s*\d+\)$/i.test(func)) {
          return "Invalid name syntax";
        }
      }
    }

    return "";
  } catch {
    return "Invalid query syntax";
  }
};

const removeSearchTerm = (index: number) => {
  searchTerms.value.splice(index, 1);
};

const transferTerm = (predicates: Predicate[], index: number) => {
  for (const predicate of predicates) {
    if (predicate.type === "name") {
      columnFilter.value = {
        column: predicate.column,
        threshold: predicate.threshold.toString(),
      };
    } else {
      percentileFilter.value = {
        percentile: predicate.percentile.toString(),
        comparison: predicate.comparison,
        value: predicate.value.toString(),
      };
    }
  }
  removeSearchTerm(index);
};

const isColumnFilterValid = computed(() => {
  const f = columnFilter.value;
  return f.column?.trim() && f.threshold !== "" && !isNaN(Number(f.threshold));
});

const isPercentileFilterValid = computed(() => {
  const f = percentileFilter.value;
  return (
    f.percentile !== "" &&
    parseFloat(f.percentile) >= 0 &&
    parseFloat(f.percentile) <= 1 &&
    f.comparison &&
    f.value !== "" &&
    !isNaN(Number(f.value))
  );
});

const addFilters = () => {
  const predicates: Predicate[] = [];

  if (isColumnFilterValid.value) {
    predicates.push({
      type: "name",
      column: columnFilter.value.column,
      threshold: parseFloat(columnFilter.value.threshold),
    });
    columnFilter.value = { column: "", threshold: "" };
  }

  if (isPercentileFilterValid.value) {
    predicates.push({
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
  }

  if (predicates.length > 0) {
    searchTerms.value.push({ predicates });
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
  fainder_mode.value = String(temp_fainder_mode.value);
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
      enable_highlighting: String(temp_enable_highlighting.value),
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

.no-scrollbar {
  overflow: hidden;
  overflow-y: hidden;
  /* Hide scrollbar for Chrome, Safari and Opera */
  &::-webkit-scrollbar {
    display: none;
  }
  /* Hide scrollbar for IE, Edge and Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  scrollbar-width: none; /* Firefox */
}

.search-input {
  max-height: v-bind(textareaMaxHeight);
  overflow: v-bind("number_of_rows === 1 ? 'hidden' : 'auto'") !important;
  overflow-y: v-bind("number_of_rows === 1 ? 'hidden' : 'auto'") !important;
  scrollbar-width: v-bind("number_of_rows === 1 ? 'none' : 'auto'") !important;
}

.error-message {
  color: rgb(var(--v-theme-error));
  font-size: 12px;
  margin-top: 4px;
  min-height: 20px;
  padding-left: 16px;
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
:deep(.function) {
  color: #569cd6;
}
:deep(.string) {
  color: #ce9178;
}
:deep(.comparison) {
  color: #c586c0;
}
:deep(.number) {
  color: #b5cea8;
}
:deep(.field) {
  color: #9cdcfe;
}
:deep(.not-operator) {
  color: #c586c0;
}
:deep(.operator) {
  color: #c586c0;
}
:deep(.bracket-0) {
  color: #ffd700;
}
:deep(.bracket-1) {
  color: #da70d6;
}
:deep(.bracket-2) {
  color: #87cefa;
}
:deep(.bracket-3) {
  color: #fa8072;
}
</style>
