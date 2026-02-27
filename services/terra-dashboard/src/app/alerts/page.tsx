'use client';

import { useEffect, useState, useCallback } from 'react';

const API_BASE = '/api/ops';

async function fetchAlerts(page = 0, size = 30) {
  const res = await fetch(`${API_BASE}/alerts?page=${page}&size=${size}`);
  if (!res.ok) throw new Error(`alerts: ${res.status}`);
  return res.json();
}

async function fetchInsights(page = 0, size = 20) {
  const res = await fetch(`${API_BASE}/insights?page=${page}&size=${size}`);
  if (!res.ok) throw new Error(`insights: ${res.status}`);
  return res.json();
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'alerts' | 'insights'>('alerts');

  const load = useCallback(async () => {
    try {
      const [a, i] = await Promise.allSettled([fetchAlerts(), fetchInsights()]);
      if (a.status === 'fulfilled') {
        const data = a.value;
        setAlerts(Array.isArray(data) ? data : data?.content ?? []);
      }
      if (i.status === 'fulfilled') {
        const data = i.value;
        setInsights(Array.isArray(data) ? data : data?.content ?? []);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 15_000);
    return () => clearInterval(iv);
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">🔔 알림 센터</h1>
        <button onClick={() => { setLoading(true); load(); }}
          className="px-4 py-2 bg-terra-600 text-white rounded-lg text-sm hover:bg-terra-700 transition">
          🔄 새로고침
        </button>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
        <button
          onClick={() => setTab('alerts')}
          className={`flex-1 py-2 rounded-md text-sm font-medium transition ${
            tab === 'alerts' ? 'bg-white shadow text-terra-700' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          ⚠️ 알림 ({alerts.length})
        </button>
        <button
          onClick={() => setTab('insights')}
          className={`flex-1 py-2 rounded-md text-sm font-medium transition ${
            tab === 'insights' ? 'bg-white shadow text-terra-700' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          💡 AI 인사이트 ({insights.length})
        </button>
      </div>

      {loading ? (
        <div className="text-gray-400 animate-pulse text-center py-8">로딩중...</div>
      ) : tab === 'alerts' ? (
        <AlertList alerts={alerts} />
      ) : (
        <InsightList insights={insights} />
      )}
    </div>
  );
}

function AlertList({ alerts }: { alerts: any[] }) {
  if (alerts.length === 0) return (
    <div className="card card-body text-gray-400 text-center py-10">
      알림이 없습니다
    </div>
  );

  return (
    <div className="space-y-2">
      {alerts.map((a: any, idx: number) => {
        const sev = a.severity ?? a.level ?? 'INFO';
        const sevCls: Record<string, string> = {
          CRITICAL: 'border-l-red-500 bg-red-50',
          WARNING:  'border-l-orange-400 bg-orange-50',
          INFO:     'border-l-blue-400 bg-blue-50',
        };
        const sevBadge: Record<string, string> = {
          CRITICAL: 'bg-red-100 text-red-700',
          WARNING:  'bg-orange-100 text-orange-700',
          INFO:     'bg-blue-100 text-blue-700',
        };
        return (
          <div key={a.alertId ?? idx}
               className={`card card-body border-l-4 ${sevCls[sev] ?? sevCls.INFO}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sevBadge[sev] ?? sevBadge.INFO}`}>
                    {sev}
                  </span>
                  <span className="text-sm font-medium text-gray-800">{a.alertType ?? a.type ?? '알림'}</span>
                </div>
                <p className="text-sm text-gray-600">{a.message ?? a.description ?? '-'}</p>
                {a.farmId && (
                  <div className="text-xs text-gray-400">
                    농장: {a.farmId} {a.sensorId ? ` | 센서: ${a.sensorId}` : ''}
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-400 whitespace-nowrap">
                {a.createdAt ? new Date(a.createdAt).toLocaleString('ko-KR') : ''}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function InsightList({ insights }: { insights: any[] }) {
  if (insights.length === 0) return (
    <div className="card card-body text-gray-400 text-center py-10">
      AI 인사이트가 없습니다
    </div>
  );

  return (
    <div className="space-y-2">
      {insights.map((ins: any, idx: number) => {
        const conf = ins.confidence != null ? Math.round(ins.confidence * 100) : null;
        return (
          <div key={ins.insightId ?? idx}
               className="card card-body border-l-4 border-l-terra-400 bg-terra-50/50">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-terra-100 text-terra-700 rounded-full text-xs font-medium">
                    {ins.insightType ?? ins.category ?? 'AI'}
                  </span>
                  {conf !== null && (
                    <span className="text-xs text-gray-400">신뢰도 {conf}%</span>
                  )}
                </div>
                <p className="text-sm text-gray-800 font-medium">{ins.summary ?? ins.title ?? '-'}</p>
                <p className="text-sm text-gray-600">{ins.description ?? ins.detail ?? ''}</p>
                {ins.recommendation && (
                  <p className="text-sm text-terra-700 mt-1">💡 {ins.recommendation}</p>
                )}
              </div>
              <div className="text-xs text-gray-400 whitespace-nowrap">
                {ins.createdAt ? new Date(ins.createdAt).toLocaleString('ko-KR') : ''}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
