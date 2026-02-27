'use client';

import { useEffect, useState } from 'react';
import { ops } from '@/lib/api';

export default function CropsPage() {
  const [crops, setCrops] = useState<any[]>([]);
  const [farmCrops, setFarmCrops] = useState<any[]>([]);
  const [conditions, setConditions] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const farmId = 'farm-A';

  useEffect(() => {
    async function load() {
      try {
        const [c, fc, cond] = await Promise.allSettled([
          ops.crops(),
          ops.farmCrops(farmId),
          ops.optimalConditions(farmId),
        ]);
        if (c.status === 'fulfilled') setCrops(Array.isArray(c.value) ? c.value : []);
        if (fc.status === 'fulfilled') setFarmCrops(Array.isArray(fc.value) ? fc.value : []);
        if (cond.status === 'fulfilled') setConditions(cond.value);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">🌱 작물 관리</h1>

      {/* 현재 농장 작물 */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">현재 재배 작물 ({farmId})</h2>
        {loading ? (
          <div className="text-gray-400 animate-pulse">로딩중...</div>
        ) : farmCrops.length === 0 ? (
          <div className="card card-body text-gray-400">등록된 작물 없음</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {farmCrops.map((fc: any, i: number) => (
              <div key={i} className="card">
                <div className="card-header flex justify-between items-center">
                  <span className="font-medium">{fc.cropProfile?.cropName ?? fc.cropCode}</span>
                  <span className="text-xs bg-terra-100 text-terra-700 px-2 py-0.5 rounded-full">
                    {fc.zone ?? '메인'}
                  </span>
                </div>
                <div className="card-body text-sm space-y-2">
                  <Row label="작물 코드" value={fc.cropCode ?? '—'} />
                  <Row label="현재 단계" value={fc.currentStageName ?? `Stage ${fc.currentStageOrder}`} />
                  <Row label="파종일" value={fc.plantedDate ?? '—'} />
                  <Row label="상태" value={fc.active ? '✅ 활성' : '❌ 비활성'} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 최적 환경 조건 */}
      {conditions && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">🎯 현재 최적 환경 조건</h2>
          <div className="card card-body">
            <pre className="text-xs bg-gray-50 p-4 rounded-lg overflow-auto">
              {JSON.stringify(conditions, null, 2)}
            </pre>
          </div>
        </section>
      )}

      {/* 전체 작물 목록 */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">전체 작물 프로필</h2>
        {crops.length === 0 ? (
          <div className="text-gray-400">작물 프로필 없음</div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="text-left px-4 py-3">작물명</th>
                  <th className="text-left px-4 py-3">코드</th>
                  <th className="text-left px-4 py-3">과/유형</th>
                  <th className="text-center px-4 py-3">활성</th>
                </tr>
              </thead>
              <tbody>
                {crops.map((c: any, i: number) => (
                  <tr key={i} className="border-t border-gray-100">
                    <td className="px-4 py-3 font-medium">{c.cropName}</td>
                    <td className="px-4 py-3 text-gray-600">{c.cropCode}</td>
                    <td className="px-4 py-3 text-gray-600">{c.family ?? '—'} / {c.cropType ?? '—'}</td>
                    <td className="px-4 py-3 text-center">{c.active ? '✅' : '❌'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
