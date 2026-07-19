'use client';

import { useEffect, useState, useCallback } from 'react';
import { ops } from '@/lib/api';

export default function ActionsPage() {
  const [pending, setPending] = useState<any[]>([]);
  const [safetyBlocked, setSafetyBlocked] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [busyPlanId, setBusyPlanId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, b, s] = await Promise.allSettled([
        ops.pendingActions(),
        ops.safetyBlockedActions(),
        ops.actionStats(),
      ]);
      if (p.status === 'fulfilled') setPending(Array.isArray(p.value) ? p.value : []);
      if (b.status === 'fulfilled') setSafetyBlocked(Array.isArray(b.value) ? b.value : []);
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
    setBusyPlanId(planId);
    try {
      await ops.approveAction(planId);
    } catch (e: any) {
      alert(`승인 실패: ${e.message}`);
    } finally {
      await load();
      setBusyPlanId(null);
    }
  }

  async function handleRevalidate(planId: string) {
    setBusyPlanId(planId);
    try {
      await ops.revalidateSafety(planId);
    } catch (e: any) {
      alert(`안전 재검증 실패: ${e.message}`);
    } finally {
      await load();
      setBusyPlanId(null);
    }
  }

  async function handleReject(planId: string) {
    const reason = prompt('거부 사유를 입력하세요:');
    if (!reason) return;
    setBusyPlanId(planId);
    try {
      await ops.rejectAction(planId, reason);
    } catch (e: any) {
      alert(`거부 실패: ${e.message}`);
    } finally {
      await load();
      setBusyPlanId(null);
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
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatBadge label="대기중" value={stats.pending} color="yellow" />
          <StatBadge label="안전 차단" value={safetyBlocked.length} color="orange" />
          <StatBadge label="실행완료" value={stats.executed} color="green" />
          <StatBadge label="거부됨" value={stats.rejected} color="gray" />
          <StatBadge label="실패" value={stats.failed} color="red" />
        </div>
      )}

      {/* 안전 재검증 대기 목록 */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          🛡️ 안전 재검증 필요 ({safetyBlocked.length}건)
        </h2>
        {loading ? (
          <div className="text-gray-400 animate-pulse">로딩중...</div>
        ) : safetyBlocked.length === 0 ? (
          <div className="card card-body text-gray-400 text-center py-6">
            안전 재검증이 필요한 액션이 없습니다
          </div>
        ) : (
          <div className="space-y-3">
            {safetyBlocked.map((plan: any) => (
              <div key={plan.planId} className="card border border-orange-200">
                <div className="card-header flex items-center justify-between bg-orange-50">
                  <div className="flex items-center gap-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700">
                      SAFETY BLOCKED
                    </span>
                    <span className="font-medium text-gray-800">{plan.actionCategory} / {plan.actionType}</span>
                  </div>
                  <span className="text-xs text-gray-400">{plan.planId?.slice(0, 12)}...</span>
                </div>
                <div className="card-body">
                  <div className="grid grid-cols-2 gap-2 text-sm text-gray-600 mb-4">
                    <div>농장: <span className="font-medium">{plan.farmId}</span></div>
                    <div>대상: <span className="font-medium">{plan.targetAssetId}</span></div>
                    <div className="col-span-2">
                      차단 사유: <span className="font-medium text-orange-700">
                        {plan.safetyBlockReasonCode || 'DEVICE_SAFETY_BLOCKED'}
                      </span>
                    </div>
                    <div className="col-span-2">계획 사유: <span className="text-gray-800">{plan.reasoning?.slice(0, 120)}</span></div>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleRevalidate(plan.planId)}
                      disabled={busyPlanId === plan.planId}
                      className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm hover:bg-orange-700 disabled:opacity-50 transition flex-1"
                    >
                      {busyPlanId === plan.planId ? '재검증 중...' : '🔁 안전 재검증'}
                    </button>
                    <button
                      onClick={() => handleReject(plan.planId)}
                      disabled={busyPlanId === plan.planId}
                      className="px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-lg text-sm hover:bg-red-100 disabled:opacity-50 transition flex-1"
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
                      disabled={busyPlanId === plan.planId}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 transition flex-1"
                    >
                      {busyPlanId === plan.planId ? '처리 중...' : '✅ 승인'}
                    </button>
                    <button
                      onClick={() => handleReject(plan.planId)}
                      disabled={busyPlanId === plan.planId}
                      className="px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-lg text-sm hover:bg-red-100 disabled:opacity-50 transition flex-1"
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
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
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
