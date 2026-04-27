import { QueryClient } from '@tanstack/react-query';

// Create and export queryClient so it can be used for cache clearing on logout
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30 * 1000, // 30 seconds — keeps things responsive after mutations
    },
  },
});
