'use client';

import { useEffect, useState } from 'react';
import { cortex, ops, sense } from '@/lib/api';
import { sensorLabel, sensorUnit, trendIcon } from '@/lib/utils';

/* ── 타입 ── */
interface TrendData {
  has_data: boolean;
  stats?: {
    mean: number;
    latest: number;
    direction: string;
    rate_of_change: number;
    moving_avg: number;
    is_spike: boolean;
    predicted_next: number | null;
    min: number;
    max: number;
    period: string;
  };
  message?: string;
}

interface ActionStats {
  pending: number;
  executed: number;
  rejected: number;
  failed: number;
  pending_critical?: number;
  pending_high?: number;
}

const FARM_ID = 'farm-A';
const SENSOR_TYPES = ['temperature', 'humidity', 'co2'];

export default function DashboardPage() {
  const [trends, setTrends] = useState<Record<string, TrendData>>({});
  const [actionStats, setActionStats] = useState<ActionStats | null>(null);
  const [mqttStats, setMqttStats] = useState<any>(null);
  const [aiInfo, setAiInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    try {
      // 병렬 요청
      const [trendResults, actStats, mqtt, info] = await Promise.allSettled([
        Promise.all(
          SENSOR_TYPES.map(async (t) => {
            const data = await cortex.trends(FARM_ID, t).catch(() => ({ has_data: false }));
            return [t, data] as const;
          })
        ),
        ops.actionStats().catch(() => null),
        sense.mqttStats().catch(() => null),
        cortex.info().catch(() => null),
      ]);

      if (trendResults.status === 'fulfilled') {
        const map: Record<string, TrendData> = {};
        trendResults.value.forEach(([k, v]) => (map[k] = v));
        setTrends(map);
      }
      if (actStats.status === 'fulfilled') setActionStats(actStats.value);
      if (mqtt.status === 'fulfilled') setMqttStats(mqtt.value);
      if (info.status === 'fulfilled') setAiInfo(info.value);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 15_000); // 15초마다 갱신
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="space-y-6">
      {/* ── 페이지 헤더 ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">실시간 대시보드</h1>
          <p className="text-sm text-gray-500 mt-1">
            {FARM_ID} — 센서 추세 · AI 파이프라인 · 제어 현황
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); loadData(); }}
          className="px-4 py-2 bg-terra-600 text-white rounded-lg text-sm hover:bg-terra-700 transition"
        >
          🔄 새로고침
        </button>
      </div>

      {/* ── 센서 추세 카드 ── */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">📊 센서 추세 (최근 1시간)</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SENSOR_TYPES.map((type) => {
            const t = trends[type];
            const s = t?.stats;
            return (
              <div key={type} className="card">
                <div className="card-header flex items-center justify-between">
                  <span className="font-medium text-gray-700">{sensorLabel(type)}</span>
                  {s && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      s.is_spike ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {s.is_spike ? '⚡ Spike' : '✓ 정상'}
                    </span>
                  )}
                </div>
                <div className="card-body">
                  {loading && !s ? (
                    <div className="text-gray-400 text-sm animate-pulse">로딩중...</div>
                  ) : !t?.has_data ? (
                    <div className="text-gray-400 text-sm">데이터 없음</div>
                  ) : s ? (
                    <div className="space-y-3">
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-gray-900">
                          {s.latest?.toFixed(1)}
                        </span>
                        <span className="text-sm text-gray-500">{sensorUnit(type)}</span>
                        <span className="text-lg ml-auto">{trendIcon(s.direction)}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                        <div>평균: <span className="font-medium">{s.mean?.toFixed(1)}</span></div>
                        <div>이동평균: <span className="font-medium">{s.moving_avg?.toFixed(1)}</span></div>
                        <div>범위: {s.min?.toFixed(1)} ~ {s.max?.toFixed(1)}</div>
                        <div>변화율: <span className="font-medium">{s.rate_of_change?.toFixed(2)}/h</span></div>
                      </div>
                      {s.predicted_next !== null && (
                        <div className="text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg">
                          🔮 10분 후 예측: <span className="font-bold">{s.predicted_next?.toFixed(1)}</span> {sensorUnit(type)}
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── 하단: AI 파이프라인 + 제어 현황 + MQTT ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* AI Pipeline 상태 */}
        <div className="card">
          <div className="card-header">
            <span className="font-medium text-gray-700">🧠 AI 파이프라인</span>
          </div>
          <div className="card-body text-sm space-y-2">
            {aiInfo?.ai_pipeline ? (
              <>
                <Row label="Local Analyzer" value={aiInfo.ai_pipeline.stage_1?.always_runs ? '✅ 활성' : '❌'} />
                <Row label="Cloud LLM" value={aiInfo.ai_pipeline.stage_2?.enabled ? '✅ 활성' : '⚠️ 비활성'} />
                <Row label="Weather" value={aiInfo.ai_pipeline.weather?.enabled ? '✅ 활성' : '⚠️ 비활성'} />
                <Row label="Crop Profile" value={aiInfo.ai_pipeline.crop_profile?.enabled ? '✅ 활성' : '⚠️ 비활성'} />
                <Row label="Trend Analyzer" value={aiInfo.ai_pipeline.trend_analyzer?.enabled ? '✅ 활성' : '⚠️ 비활성'} />
              </>
            ) : (
              <div className="text-gray-400">연결 대기중...</div>
            )}
          </div>
        </div>

        {/* 액션 플랜 통계 */}
        <div className="card">
          <div className="card-header">
            <span className="font-medium text-gray-700">⚡ 제어 액션</span>
          </div>
          <div className="card-body text-sm space-y-2">
            {actionStats ? (
              <>
                <Row label="대기중 (Pending)" value={String(actionStats.pending)}
                  highlight={actionStats.pending > 0} />
                <Row label="실행완료" value={String(actionStats.executed)} />
                <Row label="거부됨" value={String(actionStats.rejected)} />
                <Row label="실패" value={String(actionStats.failed)}
                  highlight={(actionStats.failed ?? 0) > 0} />
                {(actionStats.pending_critical ?? 0) > 0 && (
                  <div className="text-xs bg-red-50 text-red-700 px-3 py-1.5 rounded-lg mt-2">
                    🚨 긴급 대기: {actionStats.pending_critical}건
                  </div>
                )}
              </>
            ) : (
              <div className="text-gray-400">연결 대기중...</div>
            )}
          </div>
        </div>

        {/* MQTT 게이트웨이 */}
        <div className="card">
          <div className="card-header">
            <span className="font-medium text-gray-700">📡 MQTT 게이트웨이</span>
          </div>
          <div className="card-body text-sm space-y-2">
            {mqttStats ? (
              <>
                <Row label="연결 상태" value={mqttStats.mqtt_connected ? '✅ 연결됨' : '❌ 끊김'} />
                <Row label="명령 전송" value={String(mqttStats.commands_sent ?? 0)} />
                <Row label="상태 수신" value={String(mqttStats.status_received ?? 0)} />
                <Row label="추적 디바이스" value={String(mqttStats.tracked_devices ?? 0)} />
                <Row label="에러" value={String(mqttStats.error_count ?? 0)}
                  highlight={(mqttStats.error_count ?? 0) > 0} />
              </>
            ) : (
              <div className="text-gray-400">연결 대기중...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── 헬퍼 컴포넌트 ── */
function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-500">{label}</span>
      <span className={highlight ? 'font-bold text-red-600' : 'font-medium text-gray-900'}>{value}</span>
    </div>
  );
}
