# TerraNeuron E2E Tests

이 디렉토리는 전체 시스템의 통합 테스트를 포함합니다.

## 테스트 실행 방법

### 1. 전체 시스템 실행
```bash
# 프로젝트 루트에서
docker-compose up -d
```

### 2. 시스템 안정화 대기 (약 30초)
```bash
# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

### 3. E2E 테스트 실행
```bash
# Python 3.10+ 필요
pip install requests

# 테스트 실행
python tests/neural-flow-test.py
```

## 테스트 시나리오

`neural-flow-test.py`는 다음 시나리오를 테스트합니다:

1. **데이터 수집**: 가짜 센서 데이터를 terra-sense API로 전송
2. **AI 분석**: terra-cortex가 데이터를 소비하고 이상 탐지 수행
3. **데이터 저장**: terra-ops가 분석 결과를 MySQL에 저장
4. **API 조회**: Dashboard API를 통해 저장된 데이터 확인

## 기대 결과

- ✅ 센서 데이터 전송 성공
- ✅ AI 분석 결과 생성
- ✅ 데이터베이스 저장 확인
- ✅ Dashboard API 정상 응답

## 트러블슈팅

### 연결 거부 오류
```bash
# 서비스가 완전히 시작될 때까지 대기
docker-compose logs terra-sense
docker-compose logs terra-cortex
docker-compose logs terra-ops
```

### Kafka 연결 오류
```bash
# Kafka 토픽 확인
docker exec -it terraneuron-kafka kafka-topics --list --bootstrap-server localhost:9092
```

### MySQL 연결 오류
```bash
# MySQL 접속 확인
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 terra_ops
```
