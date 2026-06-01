import { useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { ApiError } from '../api/client';
import { ErrorState } from '../components/cards/StateViews';
import { useAuth } from '../components/layout/AuthProvider';

type SubmitEvent = {
  preventDefault: () => void;
};

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const location = useLocation();
  const [loginValue, setLoginValue] = useState('admin@example.com');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/dashboard';

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ login: loginValue, password });
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : 'Не удалось войти. Проверьте доступность API.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <section className="grid w-full max-w-6xl gap-8 lg:grid-cols-2 lg:items-center">
        <div className="animate-reveal">
          <p className="section-label">Демо-версия</p>
          <h1 className="mt-4 font-display text-5xl font-bold leading-tight text-cream sm:text-6xl">
            Вся аналитика автопарка в одном месте.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
            Следите за расходом топлива, простоем, превышением скорости и рейтингом машин.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {['Вход защищён', 'Демо-данные готовы', 'Отчёты и метрики'].map((item) => (
              <div key={item} className="surface-card px-4 py-3 text-sm font-bold text-signal">
                {item}
              </div>
            ))}
          </div>
        </div>

        <form className="surface-card animate-reveal p-6 sm:p-8" onSubmit={handleSubmit}>
          <p className="section-label">Вход</p>
          <h2 className="mt-3 font-display text-3xl text-cream">Вход</h2>
          <p className="mt-3 text-sm leading-6 text-muted">Войдите под демо-аккаунтом или своим логином.</p>

          {error ? <div className="mt-5"><ErrorState title="Не удалось войти" message={error} /></div> : null}

          <label className="mt-6 block text-sm font-semibold text-cream" htmlFor="login">
            Логин Pilot-GPS
          </label>
          <input id="login" className="control-field mt-2" value={loginValue} onChange={(event) => setLoginValue(event.target.value)} required />

          <label className="mt-5 block text-sm font-semibold text-cream" htmlFor="password">
            Пароль
          </label>
          <input
            id="password"
            className="control-field mt-2"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <button className="primary-action mt-7 w-full" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Входим...' : 'Войти'}
          </button>

          <p className="mt-6 text-center text-sm text-muted">
            Нужна учётная запись?{' '}
            <Link className="font-bold text-signal hover:text-cream" to="/register">
              Зарегистрироваться
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
