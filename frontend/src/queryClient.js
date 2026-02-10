import { QueryClient } from '@tanstack/react-query';

// Create and export queryClient so it can be used for cache clearing on logout
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});
