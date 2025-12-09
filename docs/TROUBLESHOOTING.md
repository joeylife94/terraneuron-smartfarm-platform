# 🔧 TerraNeuron 트러블슈팅 가이드

자주 발생하는 문제와 해결 방법을 정리한 문서입니다.

## 📋 목차

- [일반적인 문제](#일반적인-문제)
- [서비스별 문제](#서비스별-문제)
- [인프라 문제](#인프라-문제)
- [성능 문제](#성능-문제)

## 🚨 일반적인 문제

### 1. Docker Compose가 시작되지 않음

**증상:**
```
ERROR: Couldn't connect to Docker daemon
```

**해결:**
```bash
# Docker 데몬 상태 확인
sudo systemctl status docker

# Docker 데몬 시작
sudo systemctl start docker

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
newgrp docker
```

### 2. 포트 충돌

**증상:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:8080: bind: address already in use
```

**해결:**
```bash
# 포트 사용 프로세스 확인 (Windows)
netstat -ano | findstr :8080

# 프로세스 종료 (Windows - 관리자 권한)
taskkill /PID <PID> /F

# 또는 docker-compose.yml에서 포트 변경
ports:
  - "8081:8080"  # 호스트:컨테이너
```

### 3. 컨테이너가 계속 재시작됨

**증상:**
```bash
$ docker-compose ps
NAME           STATUS
terra-ops      Restarting (1) 5 seconds ago
```

**해결:**
```bash
# 로그 확인
docker-compose logs terra-ops

# 일반적인 원인:
# 1. 데이터베이스 연결 실패 -> MySQL 컨테이너가 준비될 때까지 대기
# 2. 환경 변수 누락 -> .env 파일 확인
# 3. 메모리 부족 -> docker stats로 확인
```

## 🔧 서비스별 문제

### Terra-Sense (Java)

#### 문제: MQTT 브로커 연결 실패

**증상:**
```
Connection lost (32109) - java.net.ConnectException: Connection refused
```

**해결:**
```bash
# Mosquitto 컨테이너 상태 확인
docker-compose logs mosquitto

# Mosquitto 재시작
docker-compose restart mosquitto

# 연결 테스트
docker exec -it terraneuron-mosquitto mosquitto_pub -t test -m "hello"
```

#### 문제: InfluxDB 쓰기 실패

**증상:**
```
unauthorized: unauthorized access
```

**해결:**
```bash
# InfluxDB 토큰 확인
docker-compose logs influxdb | grep token

# application.properties에서 토큰 업데이트
influxdb.token=<correct-token>
```

### Terra-Cortex (Python)

#### 문제: Kafka 소비자가 메시지를 받지 못함

**증상:**
```
No messages consumed from topic raw-sensor-data
```

**해결:**
```bash
# Kafka 토픽 확인
docker exec -it terraneuron-kafka kafka-topics --list --bootstrap-server localhost:9092

# 토픽에 메시지가 있는지 확인
docker exec -it terraneuron-kafka kafka-console-consumer \
  --topic raw-sensor-data \
  --from-beginning \
  --bootstrap-server localhost:9092 \
  --max-messages 10

# Consumer Group 상태 확인
docker exec -it terraneuron-kafka kafka-consumer-groups \
  --describe \
  --group terra-cortex-group \
  --bootstrap-server localhost:9092
```

#### 문제: AI 모델 로딩 실패

**증상:**
```
ModuleNotFoundError: No module named 'torch'
```

**해결:**
```bash
# 컨테이너 재빌드
docker-compose build terra-cortex

# 로컬 개발 환경
cd services/terra-cortex
pip install -r requirements.txt
```

### Terra-Ops (Java)

#### 문제: MySQL 연결 실패

**증상:**
```
Communications link failure - Connection refused
```

**해결:**
```bash
# MySQL 컨테이너 상태 확인
docker-compose logs mysql

# MySQL 준비 상태 확인
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 -e "SELECT 1"

# 연결 문자열 확인 (application.properties)
spring.datasource.url=jdbc:mysql://mysql:3306/terra_ops
```

#### 문제: JPA 엔티티 매핑 오류

**증상:**
```
Table 'terra_ops.insights' doesn't exist
```

**해결:**
```bash
# MySQL 접속하여 테이블 확인
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 terra_ops

mysql> SHOW TABLES;

# 초기화 스크립트 재실행
docker-compose down -v
docker-compose up -d
```

## 🏗️ 인프라 문제

### Kafka

#### 문제: Kafka 브로커가 시작되지 않음

**증상:**
```
Timed out waiting for connection while in state: CONNECTING
```

**해결:**
```bash
# Zookeeper 먼저 확인
docker-compose logs zookeeper

# Kafka 재시작 (Zookeeper 준비 후)
docker-compose restart kafka

# Kafka 로그 확인
docker-compose logs kafka | grep -i error
```

#### 문제: 디스크 용량 부족

**증상:**
```
No space left on device
```

**해결:**
```bash
# Docker 볼륨 정리
docker system prune -a --volumes

# Kafka 데이터 보관 정책 설정 (docker-compose.yml)
environment:
  KAFKA_LOG_RETENTION_HOURS: 24
  KAFKA_LOG_RETENTION_BYTES: 1073741824  # 1GB
```

### MySQL

#### 문제: 초기화 스크립트가 실행되지 않음

**증상:**
초기 데이터가 없음

**해결:**
```bash
# 볼륨 삭제 후 재시작
docker-compose down -v
docker-compose up -d

# 수동으로 초기화 스크립트 실행
docker exec -i terraneuron-mysql mysql -u terra -pterra2025 terra_ops < infra/mysql/init.sql
```

### Prometheus & Grafana

#### 문제: Prometheus가 메트릭을 수집하지 못함

**증상:**
```
Get "http://terra-ops:8080/actuator/prometheus": dial tcp: lookup terra-ops: no such host
```

**해결:**
```bash
# 서비스 네트워크 확인
docker network inspect terraneuron-smartfarm-platform_terraneuron-net

# Prometheus 설정 확인
docker exec -it terraneuron-prometheus cat /etc/prometheus/prometheus.yml

# Actuator 엔드포인트 확인
curl http://localhost:8080/actuator/prometheus
```

#### 문제: Grafana 대시보드가 데이터를 표시하지 않음

**증상:**
No data

**해결:**
```bash
# Prometheus 데이터소스 연결 확인
# Grafana UI -> Configuration -> Data Sources -> Prometheus -> Test

# Prometheus에서 직접 쿼리 테스트
# http://localhost:9090 -> Graph -> 쿼리 입력

# 예: up{job="terra-ops"}
```

## ⚡ 성능 문제

### 메모리 부족

**증상:**
```
OOMKilled
```

**해결:**
```bash
# 컨테이너별 메모리 사용량 확인
docker stats

# docker-compose.yml에 메모리 제한 추가
services:
  terra-ops:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

### 느린 응답 시간

**증상:**
API 응답이 느림

**해결:**
```bash
# 1. 로그에서 느린 쿼리 확인
docker-compose logs terra-ops | grep "slow query"

# 2. 데이터베이스 인덱스 확인
mysql> SHOW INDEX FROM insights;

# 3. Kafka Consumer Lag 확인
docker exec -it terraneuron-kafka kafka-consumer-groups \
  --describe \
  --all-groups \
  --bootstrap-server localhost:9092

# 4. JVM 힙 메모리 조정 (docker-compose.yml)
environment:
  JAVA_OPTS: "-Xms512m -Xmx2g"
```

## 🔍 디버깅 팁

### 로그 레벨 변경

**Java (Spring Boot):**
```properties
# application.properties
logging.level.com.terraneuron=DEBUG
logging.level.org.springframework.kafka=DEBUG
```

**Python (FastAPI):**
```python
# src/main.py
logging.basicConfig(level=logging.DEBUG)
```

### 컨테이너 내부 접속

```bash
# Shell 접속
docker exec -it terra-ops bash
docker exec -it terra-cortex sh

# 특정 명령 실행
docker exec terra-ops curl http://localhost:8080/actuator/health
```

### 네트워크 연결 테스트

```bash
# 컨테이너 간 연결 테스트
docker exec terra-ops ping kafka
docker exec terra-ops nc -zv mysql 3306
```

## 📞 추가 지원

문제가 해결되지 않나요?

1. [GitHub Issues](https://github.com/joeylife94/terraneuron-smartfarm-platform/issues)에 문제 보고
2. 다음 정보를 포함해주세요:
   - OS 및 버전
   - Docker 버전
   - 에러 로그 (전체)
   - 재현 단계
   - 스크린샷 (가능한 경우)

## 🆕 RAG 시스템 관련 문제

### 문제: RAG API가 응답하지 않음

**증상:**
```bash
curl http://localhost:8082/rag/query -X POST -H "Content-Type: application/json" -d '{"query":"test"}'
# 504 Gateway Timeout
```

**해결:**
```bash
# 1. ChromaDB 볼륨 확인
docker-compose logs terra-cortex | grep chroma

# 2. 지식 베이스 재구축
docker exec -it terra-cortex python src/ingest_knowledge.py

# 3. ChromaDB 데이터 확인
docker exec -it terra-cortex ls -la data/chroma_db/
```

### 문제: Ollama LLM 느린 응답

**증상:**
LLM 응답이 10초 이상 소요

**해결:**
```bash
# 1. 더 작은 모델 사용
ollama pull mistral  # llama3.1 대신 mistral 사용

# 2. .env 파일 업데이트
OPENAI_MODEL=mistral

# 3. terra-cortex 재시작
docker-compose restart terra-cortex

# 4. GPU 가속 확인 (가능한 경우)
nvidia-smi  # NVIDIA GPU가 있는 경우
```

### 문제: 지식 베이스 업데이트 실패

**증상:**
```
Error: Cannot connect to ChromaDB
```

**해결:**
```bash
# 1. ChromaDB 볼륨 삭제 및 재생성
docker-compose down
docker volume rm terraneuron_chroma-data
docker-compose up -d terra-cortex

# 2. 지식 베이스 파일 확인
ls -la services/terra-cortex/data/knowledge_base/

# 3. 수동으로 지식 베이스 재구축
docker exec -it terra-cortex python src/ingest_knowledge.py
```

## 📚 관련 문서

- [배포 가이드](DEPLOYMENT.md)
- [기여 가이드](../CONTRIBUTING.md)
- [README](../README.md)
