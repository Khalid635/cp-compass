/* Demo layout — the full app on seeded data, read-only, honestly labelled.
   Same pages as the real app, driven by /api/demo/*. */
import { Outlet } from 'react-router-dom';
import { AppShell } from '../components/layout';
import type { Theme } from '../hooks/useTheme';

export default function DemoLayout({ theme, toggleTheme }: { theme: Theme; toggleTheme: () => void }) {
  return (
    <AppShell theme={theme} toggleTheme={toggleTheme} demo base="/demo">
      <Outlet />
    </AppShell>
  );
}
