import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import type { LoginPayload, RegisterPayload, User } from '../../api/auth';
import { login as apiLogin, logout as apiLogout, me, register as apiRegister } from '../../api/auth';
import { getToken } from '../../api/client';

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadUser() {
      if (!getToken()) {
        setIsBootstrapping(false);
        return;
      }

      try {
        const currentUser = await me();
        if (!ignore) {
          setUser(currentUser);
        }
      } catch {
        apiLogout();
        if (!ignore) {
          setUser(null);
        }
      } finally {
        if (!ignore) {
          setIsBootstrapping(false);
        }
      }
    }

    void loadUser();

    return () => {
      ignore = true;
    };
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const loggedInUser = await apiLogin(payload);
    setUser(loggedInUser);
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    await apiRegister(payload);
    const loggedInUser = await apiLogin({ login: payload.login, password: payload.password });
    setUser(loggedInUser);
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isAuthenticated: Boolean(user), isBootstrapping, login, register, logout }),
    [isBootstrapping, login, logout, register, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
