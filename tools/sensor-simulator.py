#!/usr/bin/env python3
"""
TerraNeuron 실시간 센서 데이터 시뮬레이터
다양한 시나리오를 시뮬레이션하여 연속적인 센서 데이터 생성
"""

import requests
import time
import random
from datetime import datetime, timezone
from typing import Dict, List
import json
import argparse


class SensorSimulator:
    """센서 데이터 시뮬레이터"""
    
    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url
        self.api_endpoint = f"{base_url}/api/v1/ingest/sensor-data"
        
        # 센서 정의
        self.sensors = [
            {"id": "sensor-001", "type": "temperature", "farm": "farm-A", "location": "A동-구역1"},
            {"id": "sensor-002", "type": "humidity", "farm": "farm-A", "location": "A동-구역1"},
            {"id": "sensor-003", "type": "co2", "farm": "farm-A", "location": "A동-구역1"},
            {"id": "sensor-004", "type": "temperature", "farm": "farm-B", "location": "B동-구역1"},
            {"id": "sensor-005", "type": "humidity", "farm": "farm-B", "location": "B동-구역1"},
            {"id": "sensor-006", "type": "co2", "farm": "farm-B", "location": "B동-구역2"},
            {"id": "sensor-007", "type": "soil_moisture", "farm": "farm-A", "location": "A동-구역2"},
            {"id": "sensor-008", "type": "light", "farm": "farm-B", "location": "B동-구역1"},
        ]
        
        # 정상 범위 설정
        self.normal_ranges = {
            "temperature": (18.0, 28.0),
            "humidity": (50.0, 75.0),
            "co2": (400.0, 800.0),
            "soil_moisture": (30.0, 60.0),
            "light": (200.0, 800.0),
        }
        
        # 시나리오별 이상 패턴
        self.anomaly_scenarios = {
            "heat_wave": {"temperature": 35.0, "humidity": 85.0},
            "cold_snap": {"temperature": 10.0, "humidity": 40.0},
            "high_co2": {"co2": 1500.0},
            "drought": {"soil_moisture": 15.0},
        }
    
    def generate_normal_value(self, sensor_type: str) -> float:
        """정상 범위 내 랜덤 값 생성"""
        min_val, max_val = self.normal_ranges[sensor_type]
        return round(random.uniform(min_val, max_val), 2)
    
    def generate_anomaly_value(self, sensor_type: str, scenario: str = None) -> float:
        """이상 데이터 생성"""
        if scenario and sensor_type in self.anomaly_scenarios.get(scenario, {}):
            base_value = self.anomaly_scenarios[scenario][sensor_type]
            return round(base_value + random.uniform(-2, 2), 2)
        
        # 랜덤 이상치
        min_val, max_val = self.normal_ranges[sensor_type]
        if random.choice([True, False]):
            return round(min_val - random.uniform(5, 15), 2)  # 하한선 이하
        else:
            return round(max_val + random.uniform(5, 15), 2)  # 상한선 초과
    
    def create_sensor_data(self, sensor: Dict, value: float) -> Dict:
        """센서 데이터 페이로드 생성"""
        unit_map = {
            "temperature": "°C",
            "humidity": "%",
            "co2": "ppm",
            "soil_moisture": "%",
            "light": "lux",
        }
        
        return {
            "sensorId": sensor["id"],
            "sensorType": sensor["type"],
            "value": value,
            "unit": unit_map.get(sensor["type"], "unit"),
            "farmId": sensor["farm"],
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
    
    def send_data(self, data: Dict) -> bool:
        """데이터 전송"""
        try:
            response = requests.post(self.api_endpoint, json=data, timeout=5)
            if response.status_code == 200:
                status = "✅" if data["value"] <= self.normal_ranges[data["sensorType"]][1] else "⚠️"
                print(f"{status} [{data['sensorId']}] {data['sensorType']}: {data['value']} {data['unit']}")
                return True
            else:
                print(f"❌ 전송 실패: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 에러: {e}")
            return False
    
    def run_normal_mode(self, interval: float = 5.0, duration: int = 60):
        """정상 모드: 모든 센서가 정상 범위 내 데이터 생성"""
        print("=" * 60)
        print("🌿 정상 모드 시작")
        print("=" * 60)
        
        start_time = time.time()
        count = 0
        
        while time.time() - start_time < duration:
            for sensor in self.sensors:
                value = self.generate_normal_value(sensor["type"])
                data = self.create_sensor_data(sensor, value)
                self.send_data(data)
                count += 1
            
            time.sleep(interval)
        
        print(f"\n✅ 정상 모드 완료: 총 {count}개 데이터 전송")
    
    def run_anomaly_mode(self, scenario: str = None, interval: float = 3.0, duration: int = 30):
        """이상 모드: 특정 시나리오의 이상 데이터 생성"""
        print("=" * 60)
        print(f"🚨 이상 모드 시작: {scenario or '랜덤 이상'}")
        print("=" * 60)
        
        start_time = time.time()
        count = 0
        anomaly_count = 0
        
        while time.time() - start_time < duration:
            for sensor in self.sensors:
                # 30% 확률로 이상 데이터 생성
                if random.random() < 0.3:
                    value = self.generate_anomaly_value(sensor["type"], scenario)
                    anomaly_count += 1
                else:
                    value = self.generate_normal_value(sensor["type"])
                
                data = self.create_sensor_data(sensor, value)
                self.send_data(data)
                count += 1
            
            time.sleep(interval)
        
        print(f"\n✅ 이상 모드 완료: 총 {count}개 (이상: {anomaly_count}개)")
    
    def run_mixed_mode(self, interval: float = 4.0, duration: int = 120):
        """혼합 모드: 정상과 이상이 섞인 현실적인 시뮬레이션"""
        print("=" * 60)
        print("🔄 혼합 모드 시작 (정상 + 간헐적 이상)")
        print("=" * 60)
        
        start_time = time.time()
        count = 0
        anomaly_count = 0
        
        scenarios = list(self.anomaly_scenarios.keys())
        
        while time.time() - start_time < duration:
            # 10% 확률로 시나리오 변경
            current_scenario = random.choice(scenarios) if random.random() < 0.1 else None
            
            for sensor in self.sensors:
                # 10% 확률로 이상 데이터
                if random.random() < 0.1:
                    value = self.generate_anomaly_value(sensor["type"], current_scenario)
                    anomaly_count += 1
                else:
                    value = self.generate_normal_value(sensor["type"])
                
                data = self.create_sensor_data(sensor, value)
                self.send_data(data)
                count += 1
            
            time.sleep(interval)
        
        print(f"\n✅ 혼합 모드 완료: 총 {count}개 (이상: {anomaly_count}개)")
    
    def run_stress_test(self, rate: int = 100):
        """부하 테스트: 대량의 데이터를 빠르게 전송"""
        print("=" * 60)
        print(f"💪 부하 테스트 시작: {rate}개 데이터 전송")
        print("=" * 60)
        
        start_time = time.time()
        success_count = 0
        
        for i in range(rate):
            sensor = random.choice(self.sensors)
            value = self.generate_normal_value(sensor["type"])
            data = self.create_sensor_data(sensor, value)
            
            if self.send_data(data):
                success_count += 1
        
        elapsed = time.time() - start_time
        throughput = success_count / elapsed
        
        print(f"\n✅ 부하 테스트 완료:")
        print(f"   - 총 전송: {rate}개")
        print(f"   - 성공: {success_count}개")
        print(f"   - 소요 시간: {elapsed:.2f}초")
        print(f"   - 처리량: {throughput:.2f} msg/sec")


def main():
    parser = argparse.ArgumentParser(description="TerraNeuron 센서 데이터 시뮬레이터")
    parser.add_argument("--url", default="http://localhost:8081", help="Terra-Sense API URL")
    parser.add_argument("--mode", choices=["normal", "anomaly", "mixed", "stress"], 
                        default="mixed", help="시뮬레이션 모드")
    parser.add_argument("--scenario", choices=["heat_wave", "cold_snap", "high_co2", "drought"],
                        help="이상 시나리오 (anomaly 모드)")
    parser.add_argument("--interval", type=float, default=4.0, help="데이터 전송 간격 (초)")
    parser.add_argument("--duration", type=int, default=60, help="실행 시간 (초)")
    parser.add_argument("--rate", type=int, default=100, help="부하 테스트 데이터 개수")
    
    args = parser.parse_args()
    
    simulator = SensorSimulator(base_url=args.url)
    
    try:
        if args.mode == "normal":
            simulator.run_normal_mode(interval=args.interval, duration=args.duration)
        elif args.mode == "anomaly":
            simulator.run_anomaly_mode(scenario=args.scenario, interval=args.interval, duration=args.duration)
        elif args.mode == "mixed":
            simulator.run_mixed_mode(interval=args.interval, duration=args.duration)
        elif args.mode == "stress":
            simulator.run_stress_test(rate=args.rate)
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단됨")


if __name__ == "__main__":
    main()
