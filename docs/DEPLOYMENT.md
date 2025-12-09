# 🚀 TerraNeuron 배포 가이드

프로덕션 환경에 TerraNeuron을 배포하는 완전한 가이드입니다.

## 📋 목차

- [사전 요구사항](#사전-요구사항)
- [로컬 배포](#로컬-배포)
- [클라우드 배포](#클라우드-배포)
- [Kubernetes 배포](#kubernetes-배포)
- [환경 변수 설정](#환경-변수-설정)
- [보안 설정](#보안-설정)
- [모니터링 설정](#모니터링-설정)

## ✅ 사전 요구사항

### 최소 시스템 요구사항

- **CPU**: 4 cores
- **RAM**: 8GB
- **Disk**: 50GB
- **OS**: Linux (Ubuntu 20.04+), macOS, Windows with WSL2

### 필수 소프트웨어

- Docker 24.0+
- Docker Compose 2.0+
- Git

## 🏠 로컬 배포

### 1. 저장소 클론

```bash
git clone https://github.com/joeylife94/terraneuron-smartfarm-platform.git
cd terraneuron-smartfarm-platform
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cat > .env << EOF
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092

# MySQL
MYSQL_ROOT_PASSWORD=terra2025
MYSQL_DATABASE=terra_ops
MYSQL_USER=terra
MYSQL_PASSWORD=terra2025

# InfluxDB
INFLUXDB_ADMIN_USER=admin
INFLUXDB_ADMIN_PASSWORD=terra2025
INFLUXDB_ADMIN_TOKEN=terra-token-2025

# Grafana
GF_SECURITY_ADMIN_PASSWORD=terra2025
EOF
```

### 3. 시스템 실행

```bash
# 전체 스택 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 상태 확인
docker-compose ps
```

### 4. 헬스체크

```bash
# Terra-Sense
curl http://localhost:8081/api/v1/ingest/health

# Terra-Cortex
curl http://localhost:8082/health

# Terra-Ops
curl http://localhost:8080/api/v1/health

# Grafana
open http://localhost:3000
```

## ☁️ 클라우드 배포

### AWS EC2 배포

#### 1. EC2 인스턴스 생성

- **Instance Type**: t3.medium (2 vCPU, 4GB RAM) 이상
- **OS**: Ubuntu 22.04 LTS
- **Security Group**: 포트 개방
  - 8000 (terra-gateway)
  - 8081 (terra-sense)
  - 8082 (terra-cortex)
  - 8083 (terra-ops)
  - 3000 (Grafana)
  - 9090 (Prometheus)
  - 22 (SSH)

#### 2. Docker 설치

```bash
# SSH 접속
ssh -i your-key.pem ubuntu@your-ec2-ip

# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
newgrp docker
```

#### 3. 애플리케이션 배포

```bash
# 저장소 클론
git clone https://github.com/joeylife94/terraneuron-smartfarm-platform.git
cd terraneuron-smartfarm-platform

# 환경 변수 설정 (위의 .env 파일 내용 참고)
nano .env

# 실행
docker-compose up -d
```

#### 4. 보안 강화 (선택사항)

```bash
# 방화벽 설정
sudo ufw allow 22/tcp
sudo ufw allow 8000:8083/tcp
sudo ufw allow 3000/tcp
sudo ufw enable

# SSL/TLS 인증서 설정 (Let's Encrypt)
sudo apt-get install certbot
sudo certbot certonly --standalone -d yourdomain.com

# Nginx 리버스 프록시 설정 (Optional)
sudo apt-get install nginx
# nginx.conf 편집하여 SSL 터미네이션 설정
```

### Azure Container Instances 배포

```bash
# Azure CLI 설치
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# 로그인
az login

# 리소스 그룹 생성
az group create --name terraneuron-rg --location koreacentral

# Container Registry 생성
az acr create --resource-group terraneuron-rg --name terraneuronregistry --sku Basic

# Docker 이미지 빌드 & 푸시
az acr build --registry terraneuronregistry --image terra-sense:latest ./services/terra-sense
az acr build --registry terraneuronregistry --image terra-cortex:latest ./services/terra-cortex
az acr build --registry terraneuronregistry --image terra-ops:latest ./services/terra-ops

# Container Instances 배포 (예시)
az container create \
  --resource-group terraneuron-rg \
  --name terra-ops \
  --image terraneuronregistry.azurecr.io/terra-ops:latest \
  --cpu 1 --memory 2 \
  --ports 8080 \
  --environment-variables \
    SPRING_KAFKA_BOOTSTRAP_SERVERS=your-kafka-server:9092 \
    SPRING_DATASOURCE_URL=jdbc:mysql://your-mysql:3306/terra_ops
```

## ⚓ Kubernetes 배포

### 1. 네임스페이스 생성

```bash
kubectl create namespace terraneuron
```

### 2. ConfigMap 생성

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: terraneuron-config
  namespace: terraneuron
data:
  KAFKA_BOOTSTRAP_SERVERS: "kafka:9092"
  MYSQL_DATABASE: "terra_ops"
```

### 3. Secret 생성

```bash
kubectl create secret generic terraneuron-secrets \
  --from-literal=mysql-password=terra2025 \
  --from-literal=influxdb-token=terra-token-2025 \
  -n terraneuron
```

### 4. 서비스 배포

```yaml
# k8s/terra-ops-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: terra-ops
  namespace: terraneuron
spec:
  replicas: 2
  selector:
    matchLabels:
      app: terra-ops
  template:
    metadata:
      labels:
        app: terra-ops
    spec:
      containers:
      - name: terra-ops
        image: ghcr.io/joeylife94/terraneuron-terra-ops:latest
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: terraneuron-config
        env:
        - name: SPRING_DATASOURCE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: terraneuron-secrets
              key: mysql-password
---
apiVersion: v1
kind: Service
metadata:
  name: terra-ops
  namespace: terraneuron
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: terra-ops
```

```bash
# 배포
kubectl apply -f k8s/
```

## 🔐 보안 설정

### 1. 프로덕션 비밀번호 변경

```bash
# .env 파일의 모든 비밀번호를 강력한 것으로 변경
MYSQL_ROOT_PASSWORD=<strong-random-password>
MYSQL_PASSWORD=<strong-random-password>
INFLUXDB_ADMIN_PASSWORD=<strong-random-password>
GF_SECURITY_ADMIN_PASSWORD=<strong-random-password>
```

### 2. HTTPS 설정 (Nginx Reverse Proxy)

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 방화벽 설정

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

## 📊 모니터링 설정

### Grafana 대시보드 접근

```
URL: http://your-server:3000
Username: admin
Password: terra2025 (변경 권장)
```

### Prometheus 메트릭 확인

```
URL: http://your-server:9090
```

### 알림 설정 (Slack)

```yaml
# infra/grafana/provisioning/notifiers/slack.yaml
notifiers:
  - name: Slack
    type: slack
    uid: slack_notifier
    settings:
      url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
      recipient: '#terraneuron-alerts'
```

## 🔄 업데이트 및 롤백

### 업데이트

```bash
# 최신 코드 가져오기
git pull origin main

# 재배포
docker-compose pull
docker-compose up -d
```

### 롤백

```bash
# 특정 버전으로 롤백
git checkout v1.0.0
docker-compose up -d
```

## 🧹 유지보수

### 로그 정리

```bash
# Docker 로그 크기 제한 (docker-compose.yml에 추가)
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 백업

```bash
# MySQL 백업
docker exec terraneuron-mysql mysqldump -u terra -pterra2025 terra_db > backup_$(date +%Y%m%d).sql

# InfluxDB 백업
docker exec terraneuron-influxdb influx backup /tmp/backup
docker cp terraneuron-influxdb:/tmp/backup ./influxdb_backup_$(date +%Y%m%d)

# 전체 볼륨 백업
docker run --rm -v terraneuron-mysql-data:/data -v $(pwd):/backup alpine tar czf /backup/mysql_backup_$(date +%Y%m%d).tar.gz /data
```

### 복구

```bash
# MySQL 복구
docker exec -i terraneuron-mysql mysql -u terra -pterra2025 terra_db < backup_20251209.sql

# InfluxDB 복구
docker cp ./influxdb_backup_20251209 terraneuron-influxdb:/tmp/backup
docker exec terraneuron-influxdb influx restore /tmp/backup
```

## 🌐 추가 클라우드 배포 옵션

### Google Cloud Platform (GCP)

```bash
# GKE 클러스터 생성
gcloud container clusters create terraneuron-cluster \
  --zone asia-northeast3-a \
  --num-nodes 3

# kubectl 설정
gcloud container clusters get-credentials terraneuron-cluster

# 배포
kubectl apply -f k8s/
```

### DigitalOcean Kubernetes

```bash
# doctl 설치 및 로그인
snap install doctl
doctl auth init

# Kubernetes 클러스터 생성
doctl kubernetes cluster create terraneuron-cluster \
  --region sgp1 \
  --node-pool "name=worker;size=s-2vcpu-4gb;count=3"

# 배포
kubectl apply -f k8s/
```

## 📚 추가 참고 자료

- [Docker Compose 문서](https://docs.docker.com/compose/)
- [Kubernetes 공식 가이드](https://kubernetes.io/docs/)
- [TerraNeuron 트러블슈팅](TROUBLESHOOTING.md)
- [프로젝트 README](../README.md)

---

**배포 성공을 기원합니다! 🚀**
# MySQL 백업
docker exec terraneuron-mysql mysqldump -u terra -pterra2025 terra_ops > backup.sql

# InfluxDB 백업
docker exec terraneuron-influxdb influx backup /backup

# 데이터 볼륨 백업
docker run --rm --volumes-from terraneuron-mysql -v $(pwd):/backup ubuntu tar cvf /backup/mysql-backup.tar /var/lib/mysql
```

## 🆘 트러블슈팅

[TROUBLESHOOTING.md](TROUBLESHOOTING.md) 참고

## 📚 추가 리소스

- [아키텍처 문서](docs/ARCHITECTURE.md)
- [API 문서](http://your-server:8080/swagger-ui.html)
- [모니터링 대시보드](http://your-server:3000)
