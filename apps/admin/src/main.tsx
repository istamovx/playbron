import '@playbron/ui/styles.css';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';

import { App } from './app';
import { ApiError } from '@playbron/api-client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // 401/403 va limit xatolarida qayta urinishning ma'nosi yo'q
      retry: (attempt, error) => {
        if (error instanceof ApiError && (error.isAuth || error.isForbidden)) return false;
        return attempt < 2;
      },
    },
    mutations: { retry: false },
  },
});

const container = document.getElementById('root');
if (!container) throw new Error('#root topilmadi');

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
