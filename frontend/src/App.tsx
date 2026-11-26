import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { AppShell } from './components/layout';
import Landing from './pages/Landing';
import { LoginPage, RegisterPage } from './pages/Auth';
import DemoLayout from './pages/Demo';
import NotFound from './pages/NotFound';
import { Skeleton } from './components/ui';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Practice = lazy(() => import('./pages/Practice'));
const Revision = lazy(() => import('./pages/Revision'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function PageLoader() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <Skeleton className="h-[118px] w-full" />
      <Skeleton className="h-[320px] w-full" />
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function AppRoutes() {
  const { theme, toggle: toggleTheme } = useTheme();
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<Landing theme={theme} toggleTheme={toggleTheme} />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Demo — full app on seeded data, no login, read-only */}
        <Route path="/demo" element={<DemoLayout theme={theme} toggleTheme={toggleTheme} />}>
          <Route index element={<Dashboard demo />} />
          <Route path="practice" element={<Practice demo />} />
          <Route path="revision" element={<Revision demo />} />
        </Route>

        {/* Real app — JWT required */}
        <Route
          path="/app"
          element={
            <RequireAuth>
              <AppShell theme={theme} toggleTheme={toggleTheme} base="/app">
                <Outlet />
              </AppShell>
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="practice" element={<Practice />} />
          <Route path="revision" element={<Revision />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </QueryClientProvider>
  );
}
