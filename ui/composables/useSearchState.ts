import type * as Types from "~/types/types";
export const useSearchState = () => {
  const route = useRoute();

  const results = useState<Types.Result[] | null>("search-results", () => null);
  const selectedResultIndex = useState("selected-result-index", () => {
    const indexFromRoute = route.query.index;
    return indexFromRoute ? parseInt(indexFromRoute as string) : 0;
  });
  const isLoading = useState("search-loading", () => false);
  const error = useState<{ message: string; details: unknown }>(
    "search-error",
    () => ({ message: "", details: null }),
  );
  const searchTime = useState("search-time", () => 0);
  const resultCount = useState("result-count", () => 0);
  const currentPage = useState(
    "current-page",
    () => parseInt(route.query.page as string) || 1,
  );
  const totalPages = useState("total-pages", () => 1);
  const query = useState(
    "search-query",
    () => (route.query.query as string) || "",
  );
  // Initialize with route query or default value
  const fainderMode = useState(
    "index-type",
    () => (route.query.fainderMode as string) || "low_memory",
  );

  const fainderIndexName = useState(
    "fainder-index-name",
    () => (route.query.fainderIndexName as string) || "default",
  );

  // Add perPage state
  const perPage = useState("per-page", () => 10);

  const resultHighlighting = useState(
    "resultHighlighting",
    () => route.query.resultHighlighting === "true",
  );

  return {
    results,
    selectedResultIndex,
    isLoading,
    error,
    searchTime,
    resultCount,
    currentPage,
    totalPages,
    query,
    fainderMode,
    perPage,
    resultHighlighting: resultHighlighting,
    fainderIndexName,
  };
};
