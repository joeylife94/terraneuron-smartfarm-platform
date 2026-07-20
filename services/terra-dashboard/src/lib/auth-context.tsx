'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export interface DashboardUser {
  username: string;
  roles: string[];
}

interface AuthContextValue {
  user: DashboardUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  hasAnyRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<DashboardUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const response = await fetch('/api/dashboard-auth/session', {
        cache: 'no-store',
        credentials: 'same-origin',
      });
      if (!response.ok) {
        setUser(null);
        return;
      }
      const payload = await response.json() as { user?: DashboardUser };
      setUser(payload.user ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSession();
    const clear = () => setUser(null);
    window.addEventListener('terraneuron:auth-required', clear);
    return () => window.removeEventListener('terraneuron:auth-required', clear);
  }, [refreshSession]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch('/api/dashboard-auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const payload = await response.json().catch(() => ({})) as { message?: string; user?: DashboardUser };
    if (!response.ok || !payload.user) {
      throw new Error(payload.message ?? 'Login failed');
    }
    setUser(payload.user);
  }, []);

  const logout = useCallback(async () => {
    await fetch('/api/dashboard-auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    }).catch(() => null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    login,
    logout,
    refreshSession,
    hasAnyRole: (...roles: string[]) => Boolean(user?.roles.some((role) => roles.includes(role))),
  }), [user, loading, login, logout, refreshSession]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used within AuthProvider');
  return value;
}
