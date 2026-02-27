import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 센서 유형 한글명
 */
export function sensorLabel(type: string) {
  const map: Record<string, string> = {
    temperature: '온도',
    humidity: '습도',
    co2: 'CO₂',
    light: '광량',
    soil_moisture: '토양수분',
  };
  return map[type] ?? type;
}

/**
 * 센서 유형 단위
 */
export function sensorUnit(type: string) {
  const map: Record<string, string> = {
    temperature: '°C',
    humidity: '%',
    co2: 'ppm',
    light: 'lux',
    soil_moisture: '%',
  };
  return map[type] ?? '';
}

/**
 * 상태 색상
 */
export function statusColor(status: string) {
  switch (status?.toUpperCase()) {
    case 'NORMAL':  return 'text-green-600 bg-green-50';
    case 'ANOMALY': return 'text-red-600 bg-red-50';
    case 'WARNING': return 'text-yellow-600 bg-yellow-50';
    default:        return 'text-gray-600 bg-gray-50';
  }
}

/**
 * 추세 방향 아이콘
 */
export function trendIcon(direction: string) {
  switch (direction) {
    case 'rising':  return '📈';
    case 'falling': return '📉';
    case 'stable':  return '➡️';
    default:        return '—';
  }
}
