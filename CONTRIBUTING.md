# Contributing to TerraNeuron Smart Farm Platform

먼저 TerraNeuron 프로젝트에 기여해주셔서 감사합니다! 🙏

## 📋 목차

- [행동 강령](#행동-강령)
- [시작하기](#시작하기)
- [개발 워크플로우](#개발-워크플로우)
- [코딩 컨벤션](#코딩-컨벤션)
- [커밋 메시지 가이드라인](#커밋-메시지-가이드라인)
- [Pull Request 프로세스](#pull-request-프로세스)

## 🤝 행동 강령

이 프로젝트는 모든 기여자가 존중받고 환영받는 환경을 조성하기 위해 노력합니다.

### 우리의 약속

- 서로를 존중하고 배려합니다
- 건설적인 피드백을 제공합니다
- 다양한 관점과 경험을 환영합니다

## 🚀 시작하기

### 1. 저장소 Fork 및 Clone

```bash
# Fork 후 클론
git clone https://github.com/YOUR_USERNAME/terraneuron-smartfarm-platform.git
cd terraneuron-smartfarm-platform

# Upstream 추가
git remote add upstream https://github.com/joeylife94/terraneuron-smartfarm-platform.git
```

### 2. 개발 환경 설정

```bash
# 전체 시스템 실행
docker-compose up -d

# 개별 서비스 개발 (Java)
cd services/terra-sense
./gradlew bootRun

# 개별 서비스 개발 (Python)
cd services/terra-cortex
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## 🔄 개발 워크플로우

### 브랜치 전략

우리는 GitHub Flow를 따릅니다:

- `main`: 프로덕션 레디 코드
- `develop`: 개발 통합 브랜치 (선택적)
- `feature/*`: 새로운 기능 개발
- `bugfix/*`: 버그 수정
- `hotfix/*`: 긴급 수정

### 브랜치 생성

```bash
# 최신 main 가져오기
git checkout main
git pull upstream main

# 새 브랜치 생성
git checkout -b feature/add-mqtt-authentication
```

## 📝 코딩 컨벤션

### Java (Spring Boot)

- **패키지 구조**: `com.terraneuron.[service].[layer]`
- **네이밍**:
  - 클래스: PascalCase (`SensorData`, `KafkaProducerService`)
  - 메서드: camelCase (`sendSensorData`, `processInsight`)
  - 상수: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
- **Lombok**: 적극 활용 (`@Data`, `@Slf4j`, `@RequiredArgsConstructor`)

### Python (FastAPI)

- **스타일 가이드**: PEP 8
- **네이밍**:
  - 함수/변수: snake_case (`create_insight`, `sensor_data`)
  - 클래스: PascalCase (`AnomalyDetector`, `KafkaService`)
- **타입 힌트**: 모든 함수에 타입 힌트 추가
- **Docstring**: Google Style

### 공통 규칙

- **들여쓰기**: 4 spaces (Java, Python 공통)
- **최대 줄 길이**: 120자
- **주석**: 복잡한 로직에만 추가, 코드 자체가 문서가 되도록

## 💬 커밋 메시지 가이드라인

[Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따릅니다:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 코드 포맷팅 (기능 변경 없음)
- `refactor`: 코드 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드/설정 파일 수정

### 예시

```bash
feat(terra-sense): add MQTT authentication support

- Implement username/password authentication for MQTT broker
- Add configuration properties for MQTT credentials
- Update documentation

Closes #42
```

## 🔍 Pull Request 프로세스

### 1. 코드 작성 전 체크리스트

- [ ] 이슈가 이미 존재하는지 확인
- [ ] 없다면 이슈를 먼저 생성하여 논의
- [ ] 브랜치를 최신 main에서 생성

### 2. 개발 중 체크리스트

- [ ] 코딩 컨벤션 준수
- [ ] 테스트 작성 (단위 테스트 필수)
- [ ] 기존 테스트가 통과하는지 확인
- [ ] 문서 업데이트 (API 변경 시 필수)

### 3. PR 생성

```bash
# 변경사항 커밋
git add .
git commit -m "feat(terra-cortex): add CNN model for disease detection"

# Push
git push origin feature/add-cnn-model
```

**PR 템플릿:**

```markdown
## 📝 변경 사항

- 변경 내용을 간단히 설명

## 🔗 관련 이슈

Closes #123

## ✅ 테스트

- [ ] 단위 테스트 추가
- [ ] E2E 테스트 통과
- [ ] 로컬에서 전체 시스템 테스트 완료

## 📸 스크린샷 (UI 변경 시)

(스크린샷 첨부)

## 📋 체크리스트

- [ ] 코딩 컨벤션 준수
- [ ] 문서 업데이트
- [ ] 테스트 추가/업데이트
- [ ] 커밋 메시지가 Conventional Commits를 따름
```

### 4. 코드 리뷰

- 최소 1명의 승인 필요
- 모든 대화가 해결되어야 함
- CI/CD 파이프라인이 통과해야 함

## 🐛 버그 리포트

버그를 발견하셨나요? [이슈를 생성](https://github.com/joeylife94/terraneuron-smartfarm-platform/issues/new)해주세요.

**포함할 내용:**
- 재현 단계
- 예상 동작
- 실제 동작
- 환경 정보 (OS, Docker 버전 등)
- 로그 (가능한 경우)

## 💡 기능 제안

새로운 기능을 제안하고 싶으신가요?

1. [이슈를 생성](https://github.com/joeylife94/terraneuron-smartfarm-platform/issues/new)하여 논의
2. 피드백을 받은 후 구현 시작
3. PR 생성

## 📚 추가 리소스

- [프로젝트 README](README.md)
- [빠른 시작 가이드](QUICKSTART.md)
- [아키텍처 문서](docs/ARCHITECTURE.md)
- [배포 가이드](docs/DEPLOYMENT.md)

## 🙏 감사합니다!

여러분의 기여가 TerraNeuron을 더 나은 프로젝트로 만듭니다! 🌿
