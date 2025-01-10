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
            prepend-icon="mdi-magnify"
            variant="elevated"
            size="large"
          >
            Search
          </v-btn>
        </v-col>
      </v-row>
    </v-container>
  </v-main>
</template>


<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';

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

const handleKeyDown = (event) => {
  if (event.key === 'Enter') {
    searchData();
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
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
  if (!value) return true;
  
  let isValid = true;
  syntaxError.value = '';

  try {
    // Match percentile function patterns
    const percentilePattern = /(?:pp|percentile)\s*\(\s*(\d+(?:\.\d+)?)\s*;\s*(ge|gt|le|lt)\s*;\s*(\d+(?:\.\d+)?)\s*(?:;\s*([a-zA-Z0-9_]+))?\s*\)/gi;
    
    // Match keyword function patterns
    const keywordPattern = /(?:kw|keyword)\s*\(\s*([^)]+)\s*\)/gi;
    
    // Check for at least one pp/percentile or kw/keyword function
    const fullQuery = value.trim();
    const hasPercentile = percentilePattern.test(fullQuery);
    // Reset the regex lastIndex after first test
    percentilePattern.lastIndex = 0;
    const hasKeyword = keywordPattern.test(fullQuery);
    // Reset the regex lastIndex after first test
    keywordPattern.lastIndex = 0;

    if (!hasPercentile && !hasKeyword) {
      isValid = false;
      syntaxError.value = 'Query must contain at least one percentile (pp) or keyword (kw) function';
      return false;
    }
    
    // Match operators
    const operatorPattern = /\b(AND|OR|XOR|NOT)\b/gi;
    
    // Check balanced parentheses
    const openParens = (fullQuery.match(/\(/g) || []).length;
    const closeParens = (fullQuery.match(/\)/g) || []).length;
    
    if (openParens !== closeParens) {
      isValid = false;
      syntaxError.value = 'Unbalanced parentheses';
      return false;
    }

    // Split query into terms
    const terms = fullQuery.split(/\b(AND|OR|XOR)\b/i);
    
    for (const term of terms) {
      const trimmedTerm = term.trim();
      if (!trimmedTerm || operatorPattern.test(trimmedTerm)) continue;
      
      // Check if term is a valid percentile or keyword function
      const isPercentile = percentilePattern.test(trimmedTerm);
      const isKeyword = keywordPattern.test(trimmedTerm);
      
      if (!isPercentile && !isKeyword && trimmedTerm !== 'NOT') {
        isValid = false;
        syntaxError.value = `Invalid term: ${trimmedTerm}`;
        break;
      }
    }

  } catch (e) {
    isValid = false;
    syntaxError.value = 'Invalid query syntax';
  }

  return isValid;
};

const highlightSyntax = (value) => {
  if (!value) {
    highlightedQuery.value = '';
    return;
  }

  let highlighted = value
    // Highlight functions
    .replace(/(pp|percentile|kw|keyword)\s*\(/gi, '<span class="function">$1</span>(')
    // Highlight operators
    .replace(/\b(AND|OR|XOR|NOT)\b/gi, '<span class="operator">$1</span>')
    // Highlight comparison operators
    .replace(/\b(ge|gt|le|lt)\b/gi, '<span class="comparison">$1</span>')
    // Highlight numbers
    .replace(/\b(\d+(\.\d+)?)\b/g, '<span class="number">$1</span>')
    // Highlight identifiers in percentile functions
    .replace(/;\s*([a-zA-Z0-9_]+)\s*\)/g, ';<span class="field">$1</span>)');

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
  color: #d32f2f;
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.number) {
  color: #1976d2;
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.field) {
  color: #2e7d32;
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.function) {
  color: #7b1fa2;
  background-color: transparent;
  padding: 0;
}

.syntax-highlight :deep(.comparison) {
  color: #e64a19;
  background-color: transparent;
  padding: 0;
}
</style>
