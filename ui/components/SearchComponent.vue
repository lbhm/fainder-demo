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
            @click="openSettings"
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
          <v-row>
            <v-col cols="12">
              <v-select
                v-model="tempFainderConfig"
                :items="availableConfigs"
                :loading="configsLoading"
                label="Fainder Configuration"
                variant="outlined"
                :hint="`Current: ${currentConfig}`"
                persistent-hint
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-select
                v-model="tempFainderMode"
                :items="fainderModes"
                label="Fainder Mode"
                variant="outlined"
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-switch
                v-model="tempResultHighlighting"
                label="Enable Result Highlighting"
                color="primary"
              />
            </v-col>
          </v-row>

          <!-- Config change progress -->
          <v-row v-if="configChangeLoading">
            <v-col cols="12">
              <v-progress-linear indeterminate color="primary" class="mb-2" />
              <div class="text-caption text-center">
                Switching to {{ tempFainderConfig }}...
              </div>
            </v-col>
          </v-row>

          <!-- Error message -->
          <v-row v-if="configError">
            <v-col cols="12">
              <v-alert
                type="error"
                variant="tonal"
                closable
                @click:close="configError = ''"
              >
                {{ configError }}
              </v-alert>
            </v-col>
          </v-row>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            color="error"
            variant="text"
            icon="mdi-close"
            :disabled="configChangeLoading"
            @click="cancelSettings"
          />
          <v-btn
            color="success"
            variant="text"
            icon="mdi-check"
            :loading="configChangeLoading"
            @click="saveSettings"
          />
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-main>
</template>

<script setup lang="ts">
import "./SearchComponent.css";
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
  if (syntaxHighlighting.value === false) {
    return value;
  }
  let highlighted = String(value);

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

  return highlighted;
}

function registerTemplate() {
  codeInput.registerTemplate(
    "syntax-highlighted",
    new codeInput.Template(
      function (resultElement: HTMLElement) {
        /* Highlight function - with `pre code` code element */
        /* Highlight code in resultElement - code is already escaped so it doesn't become HTML */
        resultElement.innerHTML = highlightSyntax(resultElement.innerHTML);
        return resultElement.innerHTML;
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

const heightCodeInput = computed(() => {
  return `${visableRows.value * 48}px`;
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
const tempFainderMode = ref(route.query.fainderMode || "low_memory");

const visableRows = ref(props.lines);
const numberOfRows = ref(props.lines);

const searchTerms = ref<Term[]>([]);

const { fainderMode, resultHighlighting } = useSearchState();

const syntaxHighlighting = useCookie("fainderSyntaxHighlighting", {
  default: () => true,
});

console.debug("`fainderSyntaxHighlighting` cookie: ", syntaxHighlighting.value);

// Initialize fainder_mode if not already set
if (!fainderMode.value) {
  fainderMode.value = String(route.query.fainderMode) || "low_memory";
}
console.debug("Initial fainderMode:", fainderMode?.value);

const tempResultHighlighting = ref(resultHighlighting.value); // Default to true

const searchQuery = ref(props.searchQuery);
const syntaxError = computed(() => {
  if (
    !searchQuery.value ||
    searchQuery.value.trim() === "" ||
    !syntaxHighlighting.value
  ) {
    return "";
  }
  return validateSyntax(searchQuery.value);
});

const isValid = ref(true);
const showSettings = ref(false);
const fainderModes = [
  { title: "Low Memory", value: "low_memory" },
  { title: "Full Precision", value: "full_precision" },
  { title: "Full Recall", value: "full_recall" },
  { title: "Exact Results", value: "exact" },
];

// Fainder config state
const availableConfigs = ref<string[]>([]);
const currentConfig = ref<string>("");
const tempFainderConfig = ref<string>("");
const configsLoading = ref(false);
const configChangeLoading = ref(false);
const configError = ref("");

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

registerTemplate();

const config = useRuntimeConfig();

// Fetch available fainder configurations
const fetchFainderConfigs = async () => {
  configsLoading.value = true;
  try {
    const response = await $fetch<{ configs: string[]; current: string }>(
      "/fainder_configs",
      {
        baseURL: config.public.apiBase,
      },
    );
    availableConfigs.value = response.configs;
    currentConfig.value = response.current;
    tempFainderConfig.value = response.current;
  } catch (error) {
    console.error("Error fetching fainder configs:", error);
    // Fallback
    availableConfigs.value = ["default"];
    currentConfig.value = "default";
    tempFainderConfig.value = "default";
  } finally {
    configsLoading.value = false;
  }
};

// Change fainder configuration
const changeFainderConfig = async (configName: string): Promise<boolean> => {
  if (configName === currentConfig.value) {
    return true;
  }

  try {
    await $fetch("/change_fainder", {
      method: "POST",
      baseURL: config.public.apiBase,
      body: { config_name: configName },
    });

    currentConfig.value = configName;
    return true;
  } catch (error: unknown) {
    console.error("Error changing fainder config:", error);
    return false;
  }
};

// Open settings and fetch configs
const openSettings = async () => {
  showSettings.value = true;
  configError.value = ""; // Reset temporary state
  await fetchFainderConfigs();
};

// on change of syntax_highlighting value, update isValid
watch(syntaxHighlighting, (value) => {
  if (!value) {
    isValid.value = true;
  } else {
    isValid.value = !syntaxError.value;
  }
  // update query param without changing anything else
  const router = useRouter();
  const route = useRoute();
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      syntaxHighlighting: String(value),
    },
  });
  // update searchQuery to trigger update
  searchQuery.value = searchQuery.value + " ";
  searchQuery.value = searchQuery.value.slice(0, -1);
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

  if (event.key === "Enter") {
    if (!event.shiftKey) {
      event.preventDefault();
      console.debug("Enter key pressed searching", searchQuery.value);
      searchData();
    } else if (event.shiftKey) {
      if (!props.inline) {
        console.debug("Shift+Enter key pressed increasing rows");
        visableRows.value += 1; // on shift+enter, increase the number of rows
      }
      numberOfRows.value += 1;
    }
  } else if (event.key === "Backspace") {
    // Check if cursor is at the end of the last line and the line is empty
    const cursorPos = event.target.selectionStart;
    const lastLineStart = event.target.value.lastIndexOf("\n") + 1;
    const isLastLineEmpty =
      event.target.value.substring(lastLineStart).trim() === "";
    const isAtEnd = cursorPos === event.target.value.length;

    if (isLastLineEmpty && isAtEnd && visableRows.value > 1) {
      if (!props.inline) {
        visableRows.value -= 1;
      }
      numberOfRows.value -= 1;
      console.debug("Backspace key pressed decreasing rows");
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

  console.debug("Parsed query results:", {
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

  const sQuery = query;
  console.log("Search query:", sQuery);
  console.log("Index type:", fainderMode.value);
  console.log("Result Highlighting status:", resultHighlighting.value);
  emit("searchData", {
    query: sQuery,
    fainderMode: fainderMode.value,
    resultHighlighting: resultHighlighting.value,
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
  // Reset temp values
  tempFainderConfig.value = currentConfig.value;
}

async function saveSettings() {
  configChangeLoading.value = true;
  configError.value = ""; // Clear any previous error

  try {
    // Handle config change if needed
    if (tempFainderConfig.value !== currentConfig.value) {
      const success = await changeFainderConfig(tempFainderConfig.value);
      if (!success) {
        configError.value =
          "Failed to update Fainder configuration. Please try again.";
        return; // Keep dialog open to show error
      }
    }

    // Save other settings
    fainderMode.value = String(tempFainderMode.value);
    resultHighlighting.value = tempResultHighlighting.value;

    // Update route
    const route = useRoute();
    await navigateTo({
      path: route.path,
      query: {
        ...route.query,
        fainderMode: tempFainderMode.value,
        resultHighlighting: String(tempResultHighlighting.value),
      },
    });

    // Close dialog without delay and search the current query
    showSettings.value = false;
    searchData();
  } finally {
    configChangeLoading.value = false;
  }
}
</script>

<style scoped>
.search-input {
  max-height: v-bind(textareaMaxHeight);
  overflow-y: v-bind("numberOfRows === 1 ? 'hidden' : 'auto'") !important;
  overflow-x: auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
</style>
