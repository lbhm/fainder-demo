export const useSearchState = () => {
  const route = useRoute();

  const results = useState("search-results", () => null);
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
  const fainder_mode = useState(
    "index-type",
    () => (route.query.fainder_mode as string) || "low_memory",
  );

  // Add perPage state
  const perPage = useState("per-page", () => 10);

  const results_highlighting = useState(
    "results_highlighting",
    () => route.query.results_highlighting === "true",
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
    fainder_mode,
    perPage,
    results_highlighting,
  };
};
