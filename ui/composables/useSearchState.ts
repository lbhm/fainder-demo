export const useSearchState = () => {
  const route = useRoute()
  
  const results = useState('search-results', () => null)
  const selectedResultIndex = useState('selected-result-index', () => {
    const indexFromRoute = route.query.index;
    return indexFromRoute ? parseInt(indexFromRoute as string) : 0;
  });
  const isLoading = useState('search-loading', () => false)
  const error = useState('search-error', () => null)
  const searchTime = useState('search-time', () => 0)
  const resultCount = useState('result-count', () => 0)
  const currentPage = useState('current-page', () => parseInt(route.query.page as string) || 1
    )
  const totalPages = useState('total-pages', () => 1)
  const query = useState('search-query', () => 
    route.query.query as string || ''
)
  // Initialize with route query or default value
  const indexType = useState('index-type', () => 
    route.query.index_type as string || 'rebinning'
  )

  // Add perPage state
  const perPage = useState('per-page', () => 10)

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
    indexType,
    perPage
  }
}
