# Search page for datasets search by precentile predicates and search by key words
# The search page will contain multiple search bars

<template>
  <v-main :class="['search-main', { 'pa-3': inline }]">
    <v-container :class="{ 'pa-2': inline }">
      <v-row :class="{ 'inline-layout': inline }">
        <v-col :cols="inline ? 10 : 12">
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

        <v-col :cols="inline ? 2 : 12">
          <v-btn
            @click="searchData"
            :block="!inline"
            :class="{ 'search-btn': inline }"
            color="primary"
            icon="mdi-magnify"
            variant="elevated"
            size="large"
          >
          </v-btn>
        </v-col>
      </v-row>
    </v-container>
  </v-main>
</template>


<script setup>
import { onMounted, onUnmounted, ref } from 'vue';

const props = defineProps({
  searchQuery: String,
  inline: {
    type: Boolean,
    default: false
  }
});
const emit = defineEmits(['searchData']);

const searchQuery = ref(props.searchQuery);
const syntaxError = ref('');
const highlightedQuery = ref('');
const highlightEnabled = useCookie('highlight-enabled');
const isValid = ref(true);

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
  emit('searchData', {
    query: searchQuery.value
  });
}

const validateSyntax = (value) => {
  if (!value) {
    syntaxError.value = '';
    isValid.value = true;
    return true;
  }
  if (value.trim() === '') {
    syntaxError.value = '';
    isValid.value = true;
    return true;
  }
  if (!highlightEnabled.value) {
    syntaxError.value = '';
    isValid.value = true;
    return true;
  }

  // Reset state
  syntaxError.value = '';
  isValid.value = true;

  try {
    // Match percentile function patterns
    const percentilePattern = /(?:pp|percentile)\s*\(\s*(\d+(?:\.\d+)?)\s*;\s*(ge|gt|le|lt)\s*;\s*(\d+(?:\.\d+)?)\s*(?:;\s*([a-zA-Z0-9_]+))?\s*\)/gi;

    // Match keyword function patterns
    const keywordPattern = /(?:kw|keyword)\s*\(\s*([^)]+)\s*\)/gi;

    // Match column function patterns
    const columnPattern = /(?:col|column)\s*\(\s*([a-zA-Z0-9_]+)\s*;\s*(\d+)\s*\)/gi;

    // Check for at least one pp/percentile or kw/keyword or col/column function
    const fullQuery = value.trim();
    const hasPercentile = percentilePattern.test(fullQuery);
    percentilePattern.lastIndex = 0;
    const hasKeyword = keywordPattern.test(fullQuery);
    keywordPattern.lastIndex = 0;
    const hasColumn = columnPattern.test(fullQuery);
    columnPattern.lastIndex = 0;

    if (!hasPercentile && !hasKeyword && !hasColumn) {
      isValid.value = false;
      syntaxError.value = 'Query must contain at least one percentile (pp), keyword (kw), or column (col) function';
      return false;
    }

    // Match operators
    const operatorPattern = /\b(AND|OR|XOR|NOT)\b/gi;

    // Check balanced parentheses
    const openParens = (fullQuery.match(/\(/g) || []).length;
    const closeParens = (fullQuery.match(/\)/g) || []).length;

    if (openParens !== closeParens) {
      isValid.value = false;
      syntaxError.value = 'Unbalanced parentheses';
      return false;
    }

    // Split query into terms
    const terms = fullQuery.split(/\b(AND|OR|XOR)\b/i);

    for (const term of terms) {
      const trimmedTerm = term.trim();
      if (!trimmedTerm || operatorPattern.test(trimmedTerm)) continue;

      // Check if term is a valid percentile, keyword, or column function
      const isPercentile = percentilePattern.test(trimmedTerm);
      const isKeyword = keywordPattern.test(trimmedTerm);
      const isColumn = columnPattern.test(trimmedTerm);

      if (!isPercentile && !isKeyword && !isColumn && trimmedTerm !== 'NOT') {
        isValid.value = false;
        syntaxError.value = `Invalid term: ${trimmedTerm}`;
        break;
      }
    }

  } catch (e) {
    isValid.value = false;
    syntaxError.value = 'Invalid query syntax';
  }

  return isValid.value;
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

  // First highlight everything except brackets
  highlighted = highlighted
    .replace(/(pp|percentile|kw|keyword|col|column)\s*(?=\()/gi, '<span class="function">$1</span>')
    .replace(/\bNOT\b/gi, '<span class="not-operator">$&</span>')
    .replace(/\b(AND|OR|XOR)\b/gi, '<span class="operator">$1</span>')
    .replace(/\b(ge|gt|le|lt)\b/gi, '<span class="comparison">$1</span>')
    .replace(/\b(\d+(\.\d+)?)\b/g, '<span class="number">$1</span>')
    .replace(/;\s*([a-zA-Z0-9_]+)\s*(?=\))/g, ';<span class="field">$1</span>');

  // Then handle brackets last
  let bracketLevel = 0;
  const maxBracketLevels = 4;

  // First, handle all opening brackets with proper escaping
  let openBrackets = highlighted.split('(');
  highlighted = openBrackets[0];
  for (let i = 1; i < openBrackets.length; i++) {
    bracketLevel =
    highlighted += `<span class="bracket-${bracketLevel}">&#40;</span>${openBrackets[i]}`;
  }

  // Then, handle all closing brackets with proper escaping
  let closeBrackets = highlighted.split(')');
  highlighted = closeBrackets[0];
  bracketLevel = Math.min(maxBracketLevels, closeBrackets.length - 1);
  for (let i = 1; i < closeBrackets.length; i++) {
    bracketLevel = ((bracketLevel - 1) + maxBracketLevels) % maxBracketLevels;
    highlighted += `<span class="bracket-${bracketLevel}">&#41;</span>${closeBrackets[i]}`;
  }

  highlightedQuery.value = highlighted;
};
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
  right: 13px;
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
</style>
