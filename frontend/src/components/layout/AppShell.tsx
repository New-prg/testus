import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { RouteDataProvider } from './RouteDataProvider';
import { useAuth } from './AuthProvider';

const navItems = [
  { label: 'Дашборд', path: '/dashboard' },
  { label: 'Машины', path: '/vehicles' },
  { label: 'Отчёты', path: '/reports' },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-grain">
      <header className="sticky top-0 z-20 border-b border-line/25 bg-ink/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-signal/35 bg-signal/10 font-display text-xl text-signal shadow-glow">
              DE
            </div>
            <div>
              <p className="section-label">Аналитика автопарка</p>
              <h1 className="font-display text-xl text-cream">Центр эффективности вождения</h1>
            </div>
          </div>

          <nav className="flex flex-wrap items-center gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `rounded-pill px-4 py-2 text-sm font-semibold transition ${
                    isActive ? 'bg-signal text-ink shadow-glow' : 'text-muted hover:bg-panelStrong hover:text-cream'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3 text-sm text-muted">
            <span className="hidden sm:inline">{user?.full_name ?? user?.email}</span>
            <button className="secondary-action" type="button" onClick={handleLogout}>
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <RouteDataProvider>
          <Outlet />
        </RouteDataProvider>
      </main>
    </div>
  );
}
