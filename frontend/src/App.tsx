import { lazy, Suspense } from 'react';
import type { CSSProperties } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { AppShell } from './components/layout';
import { PaletteProvider } from './components/CommandPalette';
import Landing from './pages/Landing';
import { LoginPage, RegisterPage } from './pages/Auth';
import DemoLayout from './pages/Demo';
import NotFound from './pages/NotFound';
import { Skeleton } from './components/ui';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Practice = lazy(() => import('./pages/Practice'));
const Revision = lazy(() => import('./pages/Revision'));
const Analytics = lazy(() => import('./pages/Analytics'));
const Calendar = lazy(() => import('./pages/Calendar'));
const WeeklyReport = lazy(() => import('./pages/WeeklyReport'));
const ProblemDetail = lazy(() => import('./pages/ProblemDetail'));
const Settings = lazy(() => import('./pages/Settings'));

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
    <PaletteProvider theme={theme} toggleTheme={toggleTheme}>
      <Toaster
        position="bottom-right"
        theme={theme}
        duration={4000}
        style={
          {
            '--normal-bg': 'var(--surface)',
            '--normal-text': 'var(--text)',
            '--normal-border': 'var(--border)',
            '--success-bg': 'var(--surface)',
            '--success-text': 'var(--text)',
            '--success-border': 'var(--border)',
          } as CSSProperties
        }
      />
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
          <Route path="analytics" element={<Analytics demo />} />
          <Route path="calendar" element={<Calendar demo />} />
          <Route path="reports/weekly" element={<WeeklyReport demo />} />
          <Route path="problems/:contestId/:index" element={<ProblemDetail demo />} />
          <Route path="settings" element={<Settings demo theme={theme} toggleTheme={toggleTheme} />} />
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
          <Route path="analytics" element={<Analytics />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="reports/weekly" element={<WeeklyReport />} />
          <Route path="problems/:contestId/:index" element={<ProblemDetail />} />
          <Route path="settings" element={<Settings theme={theme} toggleTheme={toggleTheme} />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
      </Suspense>
    </PaletteProvider>
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
