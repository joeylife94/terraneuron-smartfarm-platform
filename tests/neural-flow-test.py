#!/usr/bin/env python3
"""
TerraNeuron E2E 통합 테스트
가짜 센서 데이터를 전송하고 전체 파이프라인 동작 확인

데이터 흐름:
1. HTTP -> terra-sense API
2. terra-sense -> Kafka (raw-sensor-data)
3. terra-cortex -> AI 분석 -> Kafka (processed-insights)
4. terra-ops -> MySQL 저장
5. Dashboard API 조회
"""

import requests
import time
import json
from datetime import datetime, timezone
from typing import List, Dict

# 서비스 엔드포인트
TERRA_SENSE_URL = "http://localhost:8081/api/v1/ingest/sensor-data"
TERRA_OPS_URL = "http://localhost:8080/api/v1"


def generate_sensor_data() -> List[Dict]:
    """테스트용 센서 데이터 생성"""
    return [
        {
            "sensorId": "sensor-001",
            "sensorType": "temperature",
            "value": 25.5,
            "unit": "°C",
            "farmId": "farm-A",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        {
            "sensorId": "sensor-002",
            "sensorType": "humidity",
            "value": 65.0,
            "unit": "%",
            "farmId": "farm-A",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        {
            "sensorId": "sensor-003",
            "sensorType": "temperature",
            "value": 35.0,  # 이상치: 정상 범위 초과
            "unit": "°C",
            "farmId": "farm-B",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        {
            "sensorId": "sensor-004",
            "sensorType": "co2",
            "value": 1500.0,  # 이상치: CO2 농도 높음
            "unit": "ppm",
            "farmId": "farm-A",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
    ]


def send_sensor_data(data: Dict) -> bool:
    """terra-sense API로 센서 데이터 전송"""
    try:
        response = requests.post(TERRA_SENSE_URL, json=data, timeout=5)
        if response.status_code == 200:
            print(f"✅ 전송 성공: {data['sensorId']} - {data['sensorType']}: {data['value']}")
            return True
        else:
            print(f"❌ 전송 실패: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 전송 에러: {e}")
        return False


def check_dashboard_summary() -> Dict:
    """Dashboard Summary API 조회"""
    try:
        response = requests.get(f"{TERRA_OPS_URL}/dashboard/summary", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Dashboard 조회 실패: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Dashboard 조회 에러: {e}")
        return {}


def check_insights() -> List[Dict]:
    """저장된 인사이트 조회"""
    try:
        response = requests.get(f"{TERRA_OPS_URL}/insights", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Insights 조회 실패: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Insights 조회 에러: {e}")
        return []


def run_test():
    """E2E 테스트 실행"""
    print("=" * 60)
    print("🧪 TerraNeuron E2E 통합 테스트 시작")
    print("=" * 60)
    
    # 1. 센서 데이터 전송
    print("\n[1단계] 센서 데이터 전송 중...")
    sensor_data_list = generate_sensor_data()
    success_count = 0
    
    for data in sensor_data_list:
        if send_sensor_data(data):
            success_count += 1
        time.sleep(0.5)
    
    print(f"\n📊 전송 결과: {success_count}/{len(sensor_data_list)} 성공")
    
    # 2. AI 분석 및 저장 대기
    print("\n[2단계] AI 분석 및 데이터베이스 저장 대기 (10초)...")
    for i in range(10, 0, -1):
        print(f"  ⏳ {i}초 남음...", end='\r')
        time.sleep(1)
    print("\n")
    
    # 3. Dashboard Summary 확인
    print("[3단계] Dashboard Summary 조회...")
    summary = check_dashboard_summary()
    if summary:
        print(f"  📈 전체 센서: {summary.get('totalSensors', 0)}개")
        print(f"  ✅ 활성 센서: {summary.get('activeSensors', 0)}개")
        print(f"  🧠 전체 인사이트: {summary.get('totalInsights', 0)}개")
        print(f"  🔥 치명적 이상: {summary.get('criticalInsights', 0)}개")
        print(f"  ⚠️  경고: {summary.get('warningInsights', 0)}개")
    
    # 4. 인사이트 상세 조회
    print("\n[4단계] 저장된 인사이트 조회...")
    insights = check_insights()
    if insights:
        print(f"  📋 총 {len(insights)}개의 인사이트 발견\n")
        for idx, insight in enumerate(insights[-5:], 1):  # 최근 5개만 출력
            print(f"  [{idx}] Sensor ID: {insight.get('sensorId')}")
            print(f"      Type: {insight.get('insightType')}")
            print(f"      Severity: {insight.get('severity')}")
            print(f"      Message: {insight.get('message')}")
            print(f"      Confidence: {insight.get('confidenceScore')}")
            print()
    else:
        print("  ⚠️  인사이트가 아직 저장되지 않았습니다.")
    
    # 5. 결과 요약
    print("=" * 60)
    print("✅ E2E 테스트 완료")
    print("=" * 60)
    print("\n📝 검증 포인트:")
    print("  1. terra-sense: HTTP 데이터 수신 → Kafka 전송")
    print("  2. terra-cortex: Kafka 소비 → AI 분석 → Kafka 전송")
    print("  3. terra-ops: Kafka 소비 → MySQL 저장")
    print("  4. Dashboard API: 데이터 조회 가능")
    print()


if __name__ == "__main__":
    try:
        run_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트 중단됨")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
