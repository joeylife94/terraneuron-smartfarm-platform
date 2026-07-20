'use client';

export interface DashboardUser {
  username: string;
  roles: string[];
}

interface SessionPayload {
  authenticated?: boolean;
  user?: DashboardUser;
}

const REFRESH_LOCK_NAME = 'terraneuron-dashboard-session-refresh';
let sessionFlight: Promise<DashboardUser | null> | null = null;

/**
 * Restores or rotates the HttpOnly Dashboard session through one same-origin
 * request. A module-level flight coalesces requests in one tab, while the Web
 * Locks API serializes the operation across tabs for the same origin.
 */
export function restoreDashboardSession(): Promise<DashboardUser | null> {
  if (sessionFlight) return sessionFlight;

  sessionFlight = withBrowserLock(fetchSession).finally(() => {
    sessionFlight = null;
  });
  return sessionFlight;
}

async function withBrowserLock<T>(operation: () => Promise<T>): Promise<T> {
  if (typeof navigator !== 'undefined' && navigator.locks) {
    return navigator.locks.request(REFRESH_LOCK_NAME, { mode: 'exclusive' }, operation);
  }
  return operation();
}

async function fetchSession(): Promise<DashboardUser | null> {
  const response = await fetch('/api/dashboard/auth/session', {
    cache: 'no-store',
    credentials: 'same-origin',
  });
  if (!response.ok) return null;

  const payload = await response.json() as SessionPayload;
  return payload.authenticated && payload.user ? payload.user : null;
}
