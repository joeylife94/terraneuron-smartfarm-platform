/**
 * API 클라이언트 — 백엔드 마이크로서비스 호출
 *
 * Public service reads continue through Next.js rewrites. Protected Terra-Ops
 * calls use the dashboard BFF so browser JavaScript never handles JWT values.
 */

import { restoreDashboardSession } from '@/lib/auth-client';

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? '';

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchJson<T>(url: string, opts?: RequestInit): Promise<T> {
  let response = await performFetch(url, opts);

  if (response.status === 401 && isDashboardAuthPath(url) && typeof window !== 'undefined') {
    const restored = await restoreDashboardSession();
    if (restored) response = await performFetch(url, opts);
    if (response.status === 401) {
      window.dispatchEvent(new Event('terraneuron:auth-required'));
    }
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { message?: string } | null;
    throw new ApiError(response.status, payload?.message ?? `API ${response.status}: ${response.statusText}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function performFetch(url: string, opts?: RequestInit): Promise<Response> {
  return fetch(`${BASE}${url}`, {
    ...opts,
    cache: 'no-store',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
  });
}

function isDashboardAuthPath(url: string): boolean {
  return url.startsWith('/api/dashboard/auth/') || url.startsWith('/api/dashboard/ops/');
}

/* ── terra-cortex ── */
export const cortex = {
  info: () => fetchJson<any>('/api/cortex/info'),
  health: () => fetchJson<any>('/api/cortex/health'),
  trends: (farmId: string, sensorType: string, window = '1h') =>
    fetchJson<any>(`/api/cortex/api/trends/${farmId}/${sensorType}?window=${window}`),
  dailyTrend: (farmId: string, sensorType: string, days = 7) =>
    fetchJson<any>(`/api/cortex/api/trends/${farmId}/${sensorType}/daily?days=${days}`),
  hourlyPattern: (farmId: string, sensorType: string, days = 7) =>
    fetchJson<any>(`/api/cortex/api/trends/${farmId}/${sensorType}/hourly?days=${days}`),
};

/* ── protected terra-ops through dashboard BFF ── */
const OPS = '/api/dashboard/ops';
export const ops = {
  pendingActions: () => fetchJson<any[]>(`${OPS}/actions/pending`),
  safetyBlockedActions: () => fetchJson<any[]>(`${OPS}/actions/safety-blocked`),
  actionStats: () => fetchJson<any>(`${OPS}/actions/statistics`),
  approveAction: (planId: string) =>
    fetchJson<any>(`${OPS}/actions/${planId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes: 'Approved via dashboard' }),
    }),
  revalidateSafety: (planId: string) =>
    fetchJson<any>(`${OPS}/actions/${planId}/safety/revalidate`, { method: 'POST' }),
  rejectAction: (planId: string, reason: string) =>
    fetchJson<any>(`${OPS}/actions/${planId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  crops: () => fetchJson<any>(`${OPS}/crops`),
  farmCrops: (farmId: string) => fetchJson<any>(`${OPS}/farms/${farmId}/crops`),
  optimalConditions: (farmId: string) => fetchJson<any>(`${OPS}/farms/${farmId}/optimal-conditions`),
};

/* ── terra-sense ── */
export const sense = {
  health: () => fetchJson<any>('/api/sense/ingest/health'),
  deviceStatus: () => fetchJson<any>('/api/sense/devices/status'),
  deviceDetail: (farmId: string, assetId: string) =>
    fetchJson<any>(`/api/sense/devices/status/${farmId}/${assetId}`),
  mqttStats: () => fetchJson<any>('/api/sense/devices/mqtt/stats'),
};
