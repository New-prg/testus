import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { ErrorState } from '../components/cards/StateViews';
import { useAuth } from '../components/layout/AuthProvider';

type SubmitEvent = {
  preventDefault: () => void;
};

export function RegisterPage() {
  const { register, isAuthenticated } = useAuth();
  const [fullName, setFullName] = useState('Fleet Analyst');
  const [loginValue, setLoginValue] = useState('pilot-demo-user');
  const [password, setPassword] = useState('analyst123');
  const [serverAddress, setServerAddress] = useState('https://pilot-gps.example');
  const [node, setNode] = useState('1');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register({
        full_name: fullName,
        login: loginValue,
        password,
        server_address: serverAddress,
        node: Number(node),
      });
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : 'Не удалось создать учётную запись.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <form className="surface-card w-full max-w-xl animate-reveal p-6 sm:p-8" onSubmit={handleSubmit}>
        <p className="section-label">Регистрация</p>
        <h1 className="mt-3 font-display text-4xl text-cream">Создать аккаунт</h1>
        <p className="mt-3 text-sm leading-6 text-muted">После регистрации вы сразу войдёте в систему.</p>

        {error ? <div className="mt-5"><ErrorState title="Не удалось зарегистрироваться" message={error} /></div> : null}

        <label className="mt-6 block text-sm font-semibold text-cream" htmlFor="fullName">
          Полное имя
        </label>
        <input id="fullName" className="control-field mt-2" value={fullName} onChange={(event) => setFullName(event.target.value)} />

        <label className="mt-5 block text-sm font-semibold text-cream" htmlFor="registerLogin">
          Логин Pilot-GPS
        </label>
        <input id="registerLogin" className="control-field mt-2" value={loginValue} onChange={(event) => setLoginValue(event.target.value)} required />

        <label className="mt-5 block text-sm font-semibold text-cream" htmlFor="serverAddress">
          Адрес сервера Pilot-GPS
        </label>
        <input id="serverAddress" className="control-field mt-2" value={serverAddress} onChange={(event) => setServerAddress(event.target.value)} required />

        <label className="mt-5 block text-sm font-semibold text-cream" htmlFor="pilotNode">
          Узел Pilot-GPS
        </label>
        <input id="pilotNode" className="control-field mt-2" type="number" min={1} value={node} onChange={(event) => setNode(event.target.value)} required />

        <label className="mt-5 block text-sm font-semibold text-cream" htmlFor="registerPassword">
          Пароль
        </label>
        <input
          id="registerPassword"
          className="control-field mt-2"
          type="password"
          minLength={6}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        <button className="primary-action mt-7 w-full" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Создаём аккаунт...' : 'Создать аккаунт'}
        </button>

        <p className="mt-6 text-center text-sm text-muted">
          Уже зарегистрированы?{' '}
          <Link className="font-bold text-signal hover:text-cream" to="/login">
            Войти
          </Link>
        </p>
      </form>
    </main>
  );
}
