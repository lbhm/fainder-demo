# Search page for datasets search by precentile predicates and search by key words
# The search page will contain multiple search bars

<template>
  <v-main :class="['search-main', { 'pa-3': inline }]">
    <v-container :class="{ 'pa-2': inline }">
      <v-row :class="{ 'inline-layout': inline }">
        <v-col cols="10">
          <div class="input-wrapper">
            <v-text-field
              v-model="searchQuery"
              label="Search by percentile predicates and keywords"
              variant="outlined"
              density="comfortable"
              :error="!isValid"
              :rules="[validateSyntax]"
              :error-messages="syntaxError"
              @update:model-value="highlightSyntax"
              hide-details="auto"
              class="search-input"
            />
            <div class="syntax-highlight" v-html="highlightedQuery"></div>
          </div>
        </v-col>
        <v-col cols="1">
          <v-btn
            @click="showSettings = true"
            icon
            class="ml-2"
          >
            <v-icon>mdi-cog</v-icon>
          </v-btn>
        </v-col>
        <v-col cols="1">
          <v-btn
            @click="searchData"
            icon
            class="ml-2"
          >
            <v-icon>mdi-magnify</v-icon>
          </v-btn>
        </v-col>
      </v-row>

      <!-- Query Builder Tools -->
      <v-row v-if="queryBuilder" class="query-builder mt-4">
        <v-col cols="12">
          <div class="builder-header mb-2">
            <v-icon icon="mdi-puzzle" class="mr-2" />
            <span class="text-h6">Query Builder</span>
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
        <v-card-title>{{ currentFunction?.name || 'Build Function' }}</v-card-title>
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
              :rules="[v => !!v || 'Percentile is required',
                      v => (v >= 0 && v <= 1) || 'Percentile must be between 0 and 1']"
              hide-details="auto"
            />
            <v-select
              v-model="functionParams.comparison"
              :items="['gt', 'ge', 'lt', 'le']"
              label="Comparison"
              :rules="[v => !!v || 'Comparison operator is required']"
              hide-details="auto"
              class="mt-4"
            />
            <v-text-field
              v-model="functionParams.value"
              label="Value"
              type="number"
              :rules="[v => !!v || 'Value is required']"
              hide-details="auto"
              class="mt-4"
            />
          </div>
          <!-- Keyword Function Builder -->
          <div v-if="currentFunction?.type === 'keyword'">
            <v-text-field
              v-model="functionParams.keyword"
              label="Search Terms"
              :rules="[v => !!v || 'Search terms are required']"
              hide-details="auto"
            />
          </div>
          <!-- Column Function Builder -->
          <div v-if="currentFunction?.type === 'column'">
            <v-text-field
              v-model="functionParams.column"
              label="Column Name"
              :rules="[v => !!v || 'Column name is required']"
              hide-details="auto"
            />
            <v-text-field
              v-model="functionParams.threshold"
              label="Threshold"
              type="number"
              :rules="[v => !!v || 'Threshold is required']"
              hide-details="auto"
              class="mt-4"
            />
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="error" variant="text" @click="showFunctionDialog = false">Cancel</v-btn>
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
        <v-card-title class="text-h5">
          Search Settings
        </v-card-title>

        <v-card-text>
          <v-select
            v-model="indexType"
            :items="indexTypes"
            label="Index Type"
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
import { onMounted, onUnmounted, ref, watch, nextTick, computed } from 'vue';

const props = defineProps({
  searchQuery: String,
  inline: {
    type: Boolean,
    default: false
  },
  queryBuilder: {
    type: Boolean,
    default: true
  }
});
const emit = defineEmits(['searchData']);
const route = useRoute(); // Add this

const { indexType } = useSearchState();
// Initialize indexType if not already set
if (!indexType.value) {
  indexType.value = route.query.index_type || 'rebinning';
}

const searchQuery = ref(props.searchQuery);
const syntaxError = ref('');
const highlightedQuery = ref('');
const highlightEnabled = useCookie('highlight-enabled');
const isValid = ref(true);

console.log('Initial indexType:', indexType?.value);

const showSettings = ref(false);
const indexTypes = [
  { title: 'Rebinning Index', value: 'rebinning' },
  { title: 'Conversion Index', value: 'conversion' },
];

// Query builder state
const showFunctionDialog = ref(false);
const currentFunction = ref(null);
const functionParams = ref({ value: {} }); // Initialize with nested value object

const operators = [
  { text: 'AND', color: 'primary' },
  { text: 'OR', color: 'secondary' },
  { text: 'XOR', color: 'warning' },
  { text: 'NOT', color: 'error' },
];

const functions = [
  { type: 'percentile', name: 'Percentile', color: 'indigo' },
  { type: 'keyword', name: 'Keyword', color: 'teal' },
  { type: 'column', name: 'Column', color: 'deep-purple' },
];

// Insert operator at cursor position or at end
const insertOperator = (operator) => {
  const input = document.querySelector('.search-input input');
  const cursorPos = input.selectionStart;
  const currentValue = searchQuery.value || '';
  
  const beforeCursor = currentValue.substring(0, cursorPos);
  const afterCursor = currentValue.substring(cursorPos);
  
  // Add space before operator if there's text before and it doesn't end with space
  const needsSpaceBefore = beforeCursor.length > 0 && !beforeCursor.endsWith(' ');
  // Add space after operator if there's text after and it doesn't start with space
  const needsSpaceAfter = afterCursor.length > 0 && !afterCursor.startsWith(' ');
  
  const spacedOperator = `${needsSpaceBefore ? ' ' : ''}${operator}${needsSpaceAfter ? ' ' : ''}`;
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
  currentFunction.value = functions.find(f => f.type === type);
  functionParams.value = { value: {} }; // Reset with proper structure
  showFunctionDialog.value = true;
};

// Build and insert function based on type
const validateAndInsert = () => {
  if (!isFormValid.value) return;
  
  let functionText = '';
  switch (currentFunction.value.type) {
    case 'percentile':
      functionText = `pp(${parseFloat(functionParams.value.percentile)};${functionParams.value.comparison};${parseFloat(functionParams.value.value)})`;
      break;
    case 'keyword':
      functionText = `kw(${functionParams.value.keyword.trim()})`;
      break;
    case 'column':
      functionText = `col(${functionParams.value.column.trim()};${parseFloat(functionParams.value.threshold)})`;
      break;
  }
  
  const input = document.querySelector('.search-input input');
  const cursorPos = input.selectionStart;
  const currentValue = searchQuery.value || '';
  
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

// Replace existing insertFunction with validateAndInsert
const insertFunction = validateAndInsert;

const isFormValid = computed(() => {
  if (!currentFunction.value || !functionParams.value) return false;

  switch (currentFunction.value.type) {
    case 'percentile':
      return (
        !!functionParams.value.percentile &&
        parseFloat(functionParams.value.percentile) >= 0 &&
        parseFloat(functionParams.value.percentile) <= 1 &&
        !!functionParams.value.comparison &&
        !!functionParams.value.value
      );
    case 'keyword':
      return !!functionParams.value.keyword && functionParams.value.keyword.trim() !== '';
    case 'column':
      return (
        !!functionParams.value.column &&
        functionParams.value.column.trim() !== '' &&
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
    syntaxError.value = '';
    isValid.value = true;
  } else {
    // Force validation when highlighting is enabled
    isValid.value = validateSyntax(searchQuery.value);
  }
  // Update highlighting
  highlightSyntax(searchQuery.value);
});

const handleKeyDown = (event) => {
  if (event.key === 'Enter') {
    searchData();
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
  // Initialize syntax highlighting if there's an initial search query
  if (props.searchQuery) {
    highlightSyntax(props.searchQuery);
  }
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});

async function searchData() {
  if (!searchQuery.value) return;

  const query = searchQuery.value.trim();
  // Check if query is just plain text (no operators or functions)
  const isPlainText = !/(?:pp|percentile|kw|keyword|col|column)\s*\(|AND|OR|XOR|NOT|\(|\)/.test(query);

  const processedQuery = isPlainText ? `kw(${query})` : query;
  console.log('Search query:', processedQuery);
  console.log('Index type:', indexType);
  emit('searchData', {
    query: processedQuery,
    indexType: indexType.value
  });
}

const validateSyntax = (value) => {
  if (!value || value.trim() === '' || !highlightEnabled.value) {
    syntaxError.value = '';
    isValid.value = true;
    return true;
  }

  // Reset state
  syntaxError.value = '';
  isValid.value = true;

  try {
    const query = value.trim();
    
    // If it's a simple keyword query (no special syntax), treat it as valid
    if (!query.includes('(') && !query.includes(')') && 
        !/\b(AND|OR|XOR|NOT)\b/i.test(query)) {
      return true;
    }

    // Check if it's a simple keyword function
    if (/^(kw|keyword)\s*\([^)]+\)$/i.test(query)) {
      return true;
    }

    // Rest of validation for complex queries
    const functionPattern = /(?:pp|percentile|kw|keyword|col|column)\s*\([^)]+\)/gi;
    const operatorPattern = /\b(AND|OR|XOR|NOT)\b/gi;
    const parenthesesPattern = /[()]/g;

    // For complex queries, check each component
    if (!functionPattern.test(value) &&
        !operatorPattern.test(value) &&
        !parenthesesPattern.test(value)) {
      return true;
    }

    // Check balanced parentheses
    const openParens = (value.match(/\(/g) || []).length;
    const closeParens = (value.match(/\)/g) || []).length;

    if (openParens !== closeParens) {
      isValid.value = false;
      syntaxError.value = 'Unbalanced parentheses';
      return false;
    }

    // Validate individual function patterns
    const functions = value.match(functionPattern) || [];
    for (const func of functions) {
      if (!/^(pp|percentile)\s*\(\s*\d+(\.\d+)?\s*;\s*(ge|gt|le|lt)\s*;\s*\d+(\.\d+)?\s*\)$/i.test(func) && 
          !/^(kw|keyword)\s*\([^)]+\)$/i.test(func) &&
          !/^(col|column)\s*\([^;]+;\s*\d+\)$/i.test(func)) {
        isValid.value = false;
        syntaxError.value = 'Invalid function syntax';
        return false;
      }
    }

    return true;
  } catch (e) {
    isValid.value = false;
    syntaxError.value = 'Invalid query syntax';
    return false;
  }
};

const highlightSyntax = (value) => {
  if (!value) {
    highlightedQuery.value = '';
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
    .replace(/(?:pp|percentile|kw|keyword|col|column)\s*\([^)]+\)/gi, (match) => {
      return match
        // Highlight function name
        .replace(/(pp|percentile|kw|keyword|col|column)\s*(?=\()/i, '<span class="function">$1</span>')
        // Highlight numbers
        .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="number">$1</span>')
        // Highlight comparisons
        .replace(/\b(ge|gt|le|lt)\b/gi, '<span class="comparison">$1</span>')
        // Highlight field names
        .replace(/;\s*([a-zA-Z0-9_]+)\s*(?=\))/g, ';<span class="field">$1</span>');
    })
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

function cancelSettings() {
  showSettings.value = false;
}

function saveSettings() {
  showSettings.value = false;
  emit('searchData', {
    query: searchQuery.value,
    indexType: indexType.value
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
  position: relative;
}

.search-input :deep(input) {
  position: relative;
  color: transparent !important;
  background: transparent !important;
  caret-color: black;
  z-index: 2;
  padding-left: 5 !important; /* Remove input padding */
}

.syntax-highlight {
  position: absolute;
  top: 12px;
  left: 15px;  /* Fine-tuned positioning */
  right: 0px;
  pointer-events: none;
  font-family: inherit;
  font-size: inherit;
  white-space: pre;
  z-index: 1;
  color: rgba(0, 0, 0, 0.87);
  mix-blend-mode: normal;
  letter-spacing: normal; /* Ensure normal letter spacing */
  padding-left: 5 !important; /* Remove input padding */
}

/* Remove background colors from syntax highlighting */
.syntax-highlight :deep(.operator) {
  color: #5C6BC0;  /* Indigo */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.not-operator) {
  color: #FF5252;  /* Red accent */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.number) {
  color: #00BCD4;  /* Cyan */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.field) {
  color: #66BB6A;  /* Light green */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.function) {
  color: #8E24AA;  /* Purple */
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.comparison) {
  color: #FB8C00;  /* Orange */
  background-color: transparent;
  padding: 0;
}

/* Add bracket pair colors */
.syntax-highlight :deep(.bracket-0) {
  color: #E91E63;  /* Pink */
  background-color: transparent;
}

.syntax-highlight :deep(.bracket-1) {
  color: #2196F3;  /* Blue */
  background-color: transparent;
}

.syntax-highlight :deep(.bracket-2) {
  color: #4CAF50;  /* Green */
  background-color: transparent;
}

.syntax-highlight :deep(.bracket-3) {
  color: #FFC107;  /* Amber */
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
