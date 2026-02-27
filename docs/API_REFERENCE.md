# 📡 TerraNeuron API Reference

> **📅 Last Updated:** 2026-02-27  
> **Version:** v2.1.0  
> **Base URLs:**  
> - Gateway: `http://localhost:8000`  
> - terra-sense (direct): `http://localhost:8081`  
> - terra-cortex (direct): `http://localhost:8082`  
> - terra-ops (direct): `http://localhost:8083` (host) → `8080` (container)

---

## 📋 목차

1. [Gateway 라우팅](#1-gateway-라우팅)
2. [terra-sense API](#2-terra-sense-api)
3. [terra-cortex API](#3-terra-cortex-api)
4. [terra-ops API](#4-terra-ops-api)
5. [인증 (Authentication)](#5-인증-authentication)
6. [공통 사항](#6-공통-사항)

---

## 1. Gateway 라우팅

terra-gateway (Spring Cloud Gateway)가 모든 외부 트래픽을 라우팅합니다.

| Gateway 경로 | 대상 서비스 | Rate Limit |
|-------------|-----------|------------|
| `/api/sense/**` | terra-sense:8081 | 10 replenish / 20 burst |
| `/api/cortex/**` | terra-cortex:8082 | — |
| `/api/ops/**` | terra-ops:8080 | 20 replenish / 50 burst |

> **참고:** Gateway를 통한 접근 시 경로에서 `/api/sense`, `/api/cortex`, `/api/ops` 프리픽스가 각 서비스로 전달됩니다. 직접 접근 시 아래 각 서비스의 경로를 사용하세요.

---

## 2. terra-sense API

**서비스:** IoT 센서 데이터 수집  
**Direct URL:** `http://localhost:8081`

### 2.1 센서 데이터 수집

```
POST /api/v1/ingest/sensor-data
```

센서 데이터를 수신하여 Kafka `raw-sensor-data` 토픽으로 발행합니다.

**Request Body:**
```json
{
  "sensorId": "temp-sensor-01",
  "sensorType": "temperature",
  "value": 28.5,
  "unit": "celsius",
  "farmId": "farm-001",
  "timestamp": "2026-02-27T10:30:00Z"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `sensorId` | String | ✅ | 센서 고유 ID |
| `sensorType` | String | ✅ | 센서 타입 (`temperature`, `humidity`, `co2`, `soilMoisture`, `light`) |
| `value` | Double | ✅ | 측정 값 |
| `unit` | String | ✅ | 단위 (`celsius`, `percent`, `ppm`, `lux`) |
| `farmId` | String | ✅ | 농장 ID |
| `timestamp` | String | ❌ | ISO 8601 (미입력 시 서버에서 자동 설정) |

**Response (200 OK):**
```json
{
  "status": "accepted",
  "message": "Sensor data ingested successfully",
  "sensorId": "temp-sensor-01",
  "timestamp": "2026-02-27T10:30:00Z"
}
```

**cURL 예시:**
```bash
curl -X POST http://localhost:8081/api/v1/ingest/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "sensorId": "temp-sensor-01",
    "sensorType": "temperature",
    "value": 42.5,
    "unit": "celsius",
    "farmId": "farm-001"
  }'
```

### 2.2 헬스 체크

```
GET /api/v1/ingest/health
```

**Response (200 OK):**
```json
{
  "status": "UP",
  "service": "terra-sense"
}
```

### 2.3 Actuator 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /actuator/health` | Spring Actuator 헬스 |
| `GET /actuator/info` | 서비스 정보 |
| `GET /actuator/prometheus` | Prometheus 메트릭 |

---

## 3. terra-cortex API

**서비스:** AI 분석 엔진  
**Direct URL:** `http://localhost:8082`

### 3.1 헬스 체크

```
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "terra-cortex",
  "kafka": "connected",
  "llm_provider": "openai",
  "rag_status": "ready"
}
```

### 3.2 RAG 쿼리

```
POST /rag/query
```

RAG 지식베이스에 질의합니다.

**Request Body:**
```json
{
  "query": "토마토 재배 시 적정 온도는?",
  "top_k": 3
}
```

**Response (200 OK):**
```json
{
  "query": "토마토 재배 시 적정 온도는?",
  "results": [
    {
      "content": "토마토의 적정 생육 온도는 주간 25-28°C...",
      "score": 0.87,
      "source": "sample_agricultural_guide.txt"
    }
  ],
  "rag_status": "success"
}
```

### 3.3 Prometheus 메트릭

```
GET /metrics
```

커스텀 메트릭:
- `terra_cortex_events_processed_total` — 처리된 이벤트 수
- `terra_cortex_anomalies_detected_total` — 탐지된 이상 수
- `terra_cortex_llm_calls_total` — LLM 호출 수
- `terra_cortex_inference_duration_seconds` — 추론 소요 시간

> **참고:** terra-cortex는 주로 Kafka 소비자로 동작합니다. `raw-sensor-data` 토픽을 소비하여 `processed-insights`와 `action-plans` 토픽으로 생산합니다.

---

## 4. terra-ops API

**서비스:** 운영 관리 (대시보드, 액션 플랜, 인증)  
**Direct URL:** `http://localhost:8083` (host) → `8080` (container 내부)  
**Swagger UI:** `http://localhost:8083/swagger-ui.html`

### 4.1 Dashboard & Insights API

#### 전체 인사이트 조회 (최신순)

```
GET /api/v1/dashboard/insights
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "farmId": "farm-001",
    "sensorType": "temperature",
    "status": "ANOMALY",
    "severity": "critical",
    "message": "Critical temperature anomaly: 42.5°C exceeds threshold 35°C",
    "rawValue": 42.5,
    "confidence": 0.95,
    "llmRecommendation": "Immediate ventilation required...",
    "traceId": "trace-abc123",
    "createdAt": "2026-02-27T10:30:00Z"
  }
]
```

#### 인사이트 전체 조회

```
GET /api/v1/insights
```

#### 농장별 인사이트 조회

```
GET /api/v1/insights/farm/{farmId}
```

**예시:** `GET /api/v1/insights/farm/farm-001`

#### 상태별 인사이트 조회

```
GET /api/v1/insights/status/{status}
```

**예시:** `GET /api/v1/insights/status/ANOMALY`  
**유효 값:** `NORMAL`, `ANOMALY`

#### 대시보드 통계 요약

```
GET /api/v1/dashboard/summary
```

**Response (200 OK):**
```json
{
  "totalInsights": 150,
  "normalCount": 120,
  "anomalyCount": 30,
  "criticalCount": 5,
  "lastUpdated": "2026-02-27T10:30:00Z"
}
```

---

### 4.2 Action Plan API

#### 대기 중인 플랜 조회

```
GET /api/actions/pending
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "planId": "plan-12345",
    "traceId": "trace-abc123",
    "planType": "input",
    "farmId": "farm-001",
    "targetAssetId": "fan-01",
    "targetAssetType": "device",
    "actionCategory": "ventilation",
    "actionType": "turn_on",
    "parameters": "{\"duration_minutes\": 30, \"speed_level\": \"high\"}",
    "reasoning": "Temperature anomaly detected...",
    "priority": "high",
    "status": "PENDING",
    "requiresApproval": true,
    "safetyValidationResult": "PASSED",
    "createdAt": "2026-02-27T10:30:00Z",
    "expiresAt": "2026-02-27T11:00:00Z"
  }
]
```

#### 대기 중인 플랜 조회 (페이지네이션)

```
GET /api/actions/pending/paged?page=0&size=20
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `page` | int | 0 | 페이지 번호 |
| `size` | int | 20 | 페이지 크기 |

#### 농장별 대기 플랜 조회

```
GET /api/actions/pending/farm/{farmId}
```

#### 플랜 상세 조회

```
GET /api/actions/{planId}
```

**예시:** `GET /api/actions/plan-12345`

#### 플랜 승인

```
POST /api/actions/{planId}/approve
```

4-Layer Safety Validation을 수행한 후 승인합니다.

**Request Body:**
```json
{
  "approvedBy": "admin-01",
  "approvalNote": "확인 완료. 환기 실행 승인."
}
```

**Response (200 OK):**
```json
{
  "planId": "plan-12345",
  "status": "APPROVED",
  "approvedBy": "admin-01",
  "approvedAt": "2026-02-27T10:31:00Z",
  "safetyValidation": "PASSED",
  "commandPublished": true
}
```

**실패 Response (400):**
```json
{
  "planId": "plan-12345",
  "status": "REJECTED",
  "reason": "Safety validation failed",
  "failedValidator": "context",
  "detail": "Cannot execute: unsafe environmental condition",
  "fallbackAction": "ALERT_ONLY"
}
```

#### 플랜 거부

```
POST /api/actions/{planId}/reject
```

**Request Body:**
```json
{
  "rejectedBy": "admin-01",
  "reason": "현재 상황에서 불필요한 조치로 판단"
}
```

#### 플랜 통계

```
GET /api/actions/statistics
```

**Response (200 OK):**
```json
{
  "totalPlans": 50,
  "pendingCount": 5,
  "approvedCount": 30,
  "rejectedCount": 10,
  "expiredCount": 5
}
```

#### 감사 이력 조회

```
GET /api/actions/{planId}/audit
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "planId": "plan-12345",
    "traceId": "trace-abc123",
    "eventType": "PLAN_CREATED",
    "logType": "activity",
    "description": "Action plan created: ventilation - turn_on",
    "performedBy": "system",
    "timestamp": "2026-02-27T10:30:00Z"
  },
  {
    "id": 2,
    "planId": "plan-12345",
    "traceId": "trace-abc123",
    "eventType": "PLAN_VALIDATED",
    "description": "Safety validation passed all 4 layers",
    "performedBy": "system",
    "timestamp": "2026-02-27T10:30:01Z"
  }
]
```

#### trace_id로 감사 이력 조회

```
GET /api/actions/audit/trace/{traceId}
```

---

### 4.3 인증 API

#### 로그인

```
POST /api/auth/login
```

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200 OK):**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
  "refreshToken": "eyJhbGciOiJIUzI1NiJ9...",
  "tokenType": "Bearer",
  "expiresIn": 86400
}
```

**현재 사용 가능한 계정:**

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | ADMIN |
| `operator` | `operator123` | OPERATOR |
| `viewer` | `viewer123` | VIEWER |

> ⚠️ **주의:** 현재 인메모리 하드코딩 계정입니다. DB `users` 테이블의 BCrypt 해시와 연동되어 있지 않습니다.

#### 토큰 갱신

```
POST /api/auth/refresh
```

**Request Body:**
```json
{
  "refreshToken": "eyJhbGciOiJIUzI1NiJ9..."
}
```

#### 토큰 검증

```
GET /api/auth/validate
```

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

**Response (200 OK):**
```json
{
  "valid": true,
  "username": "admin",
  "roles": ["ROLE_ADMIN"]
}
```

### 4.4 헬스 체크

```
GET /api/v1/health
```

### 4.5 Actuator 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /actuator/health` | Spring Actuator 헬스 |
| `GET /actuator/info` | 서비스 정보 |
| `GET /actuator/prometheus` | Prometheus 메트릭 |

---

## 5. 인증 (Authentication)

### JWT 토큰 사용법

1. **로그인하여 토큰 발급:**
```bash
curl -X POST http://localhost:8083/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

2. **API 호출 시 Authorization 헤더에 포함:**
```bash
curl http://localhost:8083/api/actions/pending \
  -H "Authorization: Bearer <access_token>"
```

3. **토큰 만료 시 갱신:**
```bash
curl -X POST http://localhost:8083/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refreshToken": "<refresh_token>"}'
```

### RBAC 권한 (설계 — 현재는 비활성)

| Endpoint Pattern | ADMIN | OPERATOR | VIEWER |
|-----------------|-------|----------|--------|
| `GET /api/v1/**` | ✅ | ✅ | ✅ |
| `GET /api/actions/**` | ✅ | ✅ | ✅ |
| `POST /api/actions/*/approve` | ✅ | ✅ | ❌ |
| `POST /api/actions/*/reject` | ✅ | ✅ | ❌ |
| `POST /api/auth/**` | ✅ | ✅ | ✅ |

> ⚠️ 현재 Spring Security가 `permitAll()`로 설정되어 있어 **모든 엔드포인트가 인증 없이 접근 가능**합니다.

---

## 6. 공통 사항

### Kafka 토픽

| 토픽 | Producer | Consumer | Format |
|------|----------|----------|--------|
| `raw-sensor-data` | terra-sense | terra-cortex | JSON (SensorData) |
| `processed-insights` | terra-cortex | terra-ops | JSON (Insight) |
| `action-plans` | terra-cortex | terra-ops | CloudEvents JSON |
| `terra.control.command` | terra-ops | ❌ 소비자 없음 | CloudEvents JSON |

### 에러 응답 형식

```json
{
  "timestamp": "2026-02-27T10:30:00Z",
  "status": 400,
  "error": "Bad Request",
  "message": "Validation failed for field 'sensorId'",
  "path": "/api/v1/ingest/sensor-data"
}
```

### HTTP 상태 코드

| 코드 | 의미 |
|------|------|
| 200 | 성공 |
| 201 | 생성 완료 |
| 400 | 잘못된 요청 (검증 실패) |
| 401 | 인증 실패 (토큰 없음/만료) |
| 403 | 권한 없음 (RBAC) |
| 404 | 리소스 없음 |
| 429 | Rate Limit 초과 |
| 500 | 서버 내부 오류 |

---

## 📚 관련 문서

- [ACTION_PROTOCOL.md](ACTION_PROTOCOL.md) — CloudEvents 프로토콜 상세
- [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) — 개발 환경 설정
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — 문제 해결
- [Swagger UI](http://localhost:8083/swagger-ui.html) — terra-ops OpenAPI 문서

---

*이 문서의 API 스펙은 소스코드 기반으로 작성되었습니다. 실제 동작과 다를 경우 소스코드를 우선합니다.*
