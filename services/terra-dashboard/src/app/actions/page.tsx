'use client';

import { useEffect, useState, useCallback } from 'react';
import { ops } from '@/lib/api';

export default function ActionsPage() {
  const [pending, setPending] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [p, s] = await Promise.allSettled([
        ops.pendingActions(),
        ops.actionStats(),
      ]);
      if (p.status === 'fulfilled') setPending(Array.isArray(p.value) ? p.value : []);
      if (s.status === 'fulfilled') setStats(s.value);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 10_000);
    return () => clearInterval(iv);
  }, [load]);

  async function handleApprove(planId: string) {
    try {
      await ops.approveAction(planId);
      load();
    } catch (e: any) {
      alert(`승인 실패: ${e.message}`);
    }
  }

  async function handleReject(planId: string) {
    const reason = prompt('거부 사유를 입력하세요:');
    if (!reason) return;
    try {
      await ops.rejectAction(planId, reason);
      load();
    } catch (e: any) {
      alert(`거부 실패: ${e.message}`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">⚡ 제어 액션 관리</h1>
        <button onClick={() => { setLoading(true); load(); }}
          className="px-4 py-2 bg-terra-600 text-white rounded-lg text-sm hover:bg-terra-700 transition">
          🔄 새로고침
        </button>
      </div>

      {/* 통계 요약 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatBadge label="대기중" value={stats.pending} color="yellow" />
          <StatBadge label="실행완료" value={stats.executed} color="green" />
          <StatBadge label="거부됨" value={stats.rejected} color="gray" />
          <StatBadge label="실패" value={stats.failed} color="red" />
        </div>
      )}

      {/* 대기중 액션 목록 */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          🔔 승인 대기 ({pending.length}건)
        </h2>
        {loading ? (
          <div className="text-gray-400 animate-pulse">로딩중...</div>
        ) : pending.length === 0 ? (
          <div className="card card-body text-gray-400 text-center py-8">
            ✅ 승인 대기중인 액션이 없습니다
          </div>
        ) : (
          <div className="space-y-3">
            {pending.map((plan: any) => (
              <div key={plan.planId} className="card">
                <div className="card-header flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      plan.priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                      plan.priority === 'HIGH'     ? 'bg-orange-100 text-orange-700' :
                      'bg-blue-100 text-blue-700'
                    }`}>
                      {plan.priority}
                    </span>
                    <span className="font-medium text-gray-800">{plan.actionCategory} / {plan.actionType}</span>
                  </div>
                  <span className="text-xs text-gray-400">{plan.planId?.slice(0, 12)}...</span>
                </div>
                <div className="card-body">
                  <div className="grid grid-cols-2 gap-2 text-sm text-gray-600 mb-4">
                    <div>농장: <span className="font-medium">{plan.farmId}</span></div>
                    <div>대상: <span className="font-medium">{plan.targetAssetId}</span></div>
                    <div className="col-span-2">사유: <span className="text-gray-800">{plan.reasoning?.slice(0, 120)}</span></div>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleApprove(plan.planId)}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 transition flex-1"
                    >
                      ✅ 승인
                    </button>
                    <button
                      onClick={() => handleReject(plan.planId)}
                      className="px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-lg text-sm hover:bg-red-100 transition flex-1"
                    >
                      ❌ 거부
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  const cls: Record<string, string> = {
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    green:  'bg-green-50 text-green-700 border-green-200',
    gray:   'bg-gray-50 text-gray-600 border-gray-200',
    red:    'bg-red-50 text-red-700 border-red-200',
  };
  return (
    <div className={`card card-body border ${cls[color] ?? cls.gray}`}>
      <div className="text-xs">{label}</div>
      <div className="text-2xl font-bold mt-1">{value ?? 0}</div>
    </div>
  );
}
