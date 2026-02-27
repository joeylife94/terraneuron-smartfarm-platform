/**
 * API 클라이언트 — 백엔드 마이크로서비스 호출
 *
 * Next.js rewrites로 프록시:
 *   /api/cortex/*  → terra-cortex:8082
 *   /api/ops/*     → terra-ops:8080/api
 *   /api/sense/*   → terra-sense:8081/api/v1
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? '';

async function fetchJson<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
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

/* ── terra-ops ── */
export const ops = {
  pendingActions: () => fetchJson<any>('/api/ops/actions/pending'),
  actionStats: () => fetchJson<any>('/api/ops/actions/statistics'),
  approveAction: (planId: string, approvedBy = 'dashboard-user') =>
    fetchJson<any>(`/api/ops/actions/${planId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approvedBy, notes: 'Approved via dashboard' }),
    }),
  rejectAction: (planId: string, reason: string) =>
    fetchJson<any>(`/api/ops/actions/${planId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejectedBy: 'dashboard-user', reason }),
    }),
  crops: () => fetchJson<any>('/api/ops/crops'),
  farmCrops: (farmId: string) => fetchJson<any>(`/api/ops/farms/${farmId}/crops`),
  optimalConditions: (farmId: string) => fetchJson<any>(`/api/ops/farms/${farmId}/optimal-conditions`),
};

/* ── terra-sense ── */
export const sense = {
  health: () => fetchJson<any>('/api/sense/ingest/health'),
  deviceStatus: () => fetchJson<any>('/api/sense/devices/status'),
  deviceDetail: (farmId: string, assetId: string) =>
    fetchJson<any>(`/api/sense/devices/status/${farmId}/${assetId}`),
  mqttStats: () => fetchJson<any>('/api/sense/devices/mqtt/stats'),
};
