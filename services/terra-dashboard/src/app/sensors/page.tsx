'use client';

import { useEffect, useState } from 'react';
import { cortex } from '@/lib/api';
import { sensorLabel, sensorUnit, trendIcon } from '@/lib/utils';

const FARM_ID = 'farm-A';
const SENSOR_TYPES = ['temperature', 'humidity', 'co2'];

export default function SensorsPage() {
  const [selectedType, setSelectedType] = useState('temperature');
  const [trend, setTrend] = useState<any>(null);
  const [daily, setDaily] = useState<any>(null);
  const [hourly, setHourly] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function loadSensor(type: string) {
    setLoading(true);
    try {
      const [t, d, h] = await Promise.all([
        cortex.trends(FARM_ID, type).catch(() => null),
        cortex.dailyTrend(FARM_ID, type).catch(() => null),
        cortex.hourlyPattern(FARM_ID, type).catch(() => null),
      ]);
      setTrend(t);
      setDaily(d);
      setHourly(h);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadSensor(selectedType); }, [selectedType]);

  const s = trend?.stats;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">센서 상세 분석</h1>

      {/* 센서 탭 */}
      <div className="flex gap-2">
        {SENSOR_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setSelectedType(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              selectedType === t
                ? 'bg-terra-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {sensorLabel(t)}
          </button>
        ))}
      </div>

      {/* 실시간 통계 */}
      {loading ? (
        <div className="card card-body text-gray-400 animate-pulse">데이터 로딩중...</div>
      ) : !trend?.has_data ? (
        <div className="card card-body text-gray-400">센서 데이터 없음</div>
      ) : s ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="현재값" value={`${s.latest?.toFixed(1)} ${sensorUnit(selectedType)}`} />
            <StatCard label="평균" value={`${s.mean?.toFixed(1)} ${sensorUnit(selectedType)}`} />
            <StatCard label="추세" value={`${trendIcon(s.direction)} ${s.direction}`} />
            <StatCard label="변화율" value={`${s.rate_of_change?.toFixed(2)}/h`} />
            <StatCard label="이동평균" value={`${s.moving_avg?.toFixed(1)}`} />
            <StatCard label="범위" value={`${s.min?.toFixed(1)} ~ ${s.max?.toFixed(1)}`} />
            <StatCard label="스파이크" value={s.is_spike ? '⚡ 감지!' : '✓ 정상'}
              danger={s.is_spike} />
            <StatCard label="10분 예측"
              value={s.predicted_next != null ? `${s.predicted_next.toFixed(1)}` : '—'} />
          </div>

          {/* 최근 포인트 테이블 */}
          {trend.recent_points?.length > 0 && (
            <div className="card">
              <div className="card-header font-medium text-gray-700">
                📈 최근 데이터 포인트 (최대 30개)
              </div>
              <div className="card-body overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-gray-500 border-b">
                    <tr><th className="text-left py-2">시간</th><th className="text-right py-2">값</th></tr>
                  </thead>
                  <tbody>
                    {trend.recent_points.slice(-15).reverse().map((p: any, i: number) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-1.5 text-gray-600">{p.time}</td>
                        <td className="py-1.5 text-right font-medium">{p.value?.toFixed(2)} {sensorUnit(selectedType)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 일간 통계 */}
          {daily?.data?.length > 0 && (
            <div className="card">
              <div className="card-header font-medium text-gray-700">📆 일간 평균 ({daily.days}일)</div>
              <div className="card-body overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-gray-500 border-b">
                    <tr><th className="text-left py-2">날짜</th><th className="text-right py-2">평균값</th></tr>
                  </thead>
                  <tbody>
                    {daily.data.map((d: any, i: number) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-1.5 text-gray-600">{d.time}</td>
                        <td className="py-1.5 text-right font-medium">{d.value?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 시간대별 패턴 */}
          {hourly?.pattern?.length > 0 && (
            <div className="card">
              <div className="card-header font-medium text-gray-700">⏰ 시간대별 패턴</div>
              <div className="card-body overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-gray-500 border-b">
                    <tr>
                      <th className="text-left py-2">시간</th>
                      <th className="text-right py-2">최소</th>
                      <th className="text-right py-2">평균</th>
                      <th className="text-right py-2">최대</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hourly.pattern.map((h: any, i: number) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-1.5 text-gray-600">{String(h.hour).padStart(2, '0')}:00</td>
                        <td className="py-1.5 text-right">{h.min?.toFixed(1)}</td>
                        <td className="py-1.5 text-right font-medium">{h.avg?.toFixed(1)}</td>
                        <td className="py-1.5 text-right">{h.max?.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

function StatCard({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="card card-body">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${danger ? 'text-red-600' : 'text-gray-900'}`}>{value}</div>
    </div>
  );
}
