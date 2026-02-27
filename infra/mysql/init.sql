-- TerraNeuron 운영 통제 서비스 초기 스키마
-- terra-ops 서비스용 MySQL 데이터베이스
-- Phase 2.A: CloudEvents + Safety Validation + Audit Logging

CREATE DATABASE IF NOT EXISTS terra_ops;
USE terra_ops;

-- 농장 관리 테이블
CREATE TABLE IF NOT EXISTS farms (
    farm_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_name VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 센서 정보 테이블
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_id BIGINT NOT NULL,
    sensor_type VARCHAR(50) NOT NULL,
    sensor_name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE
);

-- AI 분석 결과 저장 테이블
CREATE TABLE IF NOT EXISTS insights (
    insight_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id BIGINT NOT NULL,
    insight_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20),
    message TEXT,
    confidence_score DECIMAL(5,2),
    detected_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE,
    INDEX idx_detected_at (detected_at),
    INDEX idx_sensor_severity (sensor_id, severity)
);

-- 알림 테이블
CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    insight_id BIGINT NOT NULL,
    alert_status VARCHAR(20) DEFAULT 'PENDING',
    sent_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (insight_id) REFERENCES insights(insight_id) ON DELETE CASCADE
);

-- ============================================================
-- Phase 2.A: Action Plan Management Tables
-- ============================================================

-- Action Plans 테이블 (CloudEvents v1.0 & FarmOS 호환)
CREATE TABLE IF NOT EXISTS action_plans (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    plan_id VARCHAR(50) NOT NULL UNIQUE,
    trace_id VARCHAR(100) NOT NULL,
    farm_id VARCHAR(50) NOT NULL,
    plan_type VARCHAR(30) DEFAULT 'input',
    target_asset_id VARCHAR(50) NOT NULL,
    target_asset_type VARCHAR(30) DEFAULT 'device',
    action_category VARCHAR(30) NOT NULL,
    action_type VARCHAR(30) NOT NULL,
    parameters JSON,
    reasoning TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    priority VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    estimated_impact TEXT,
    safety_conditions JSON,
    requires_approval BOOLEAN DEFAULT TRUE,
    approved_by VARCHAR(100),
    approved_at TIMESTAMP NULL,
    rejection_reason TEXT,
    executed_at TIMESTAMP NULL,
    execution_result VARCHAR(50),
    execution_error TEXT,
    generated_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_plan_farm_id (farm_id),
    INDEX idx_plan_status (status),
    INDEX idx_plan_trace_id (trace_id),
    INDEX idx_plan_priority (priority),
    INDEX idx_plan_expires_at (expires_at)
);

-- Audit Logs 테이블 (FarmOS Log 호환: type=activity)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_id VARCHAR(50) NOT NULL UNIQUE,
    trace_id VARCHAR(100) NOT NULL,
    log_type VARCHAR(30) DEFAULT 'activity',
    event_type VARCHAR(30) NOT NULL,
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(50) NOT NULL,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(255) NOT NULL,
    details JSON,
    timestamp TIMESTAMP NOT NULL,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_trace_id (trace_id),
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_event_type (event_type),
    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_actor (actor)
);

-- ============================================================
-- Phase 3: User Management (JWT Authentication)
-- ============================================================

-- 사용자 테이블 (Production용)
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    full_name VARCHAR(100),
    roles VARCHAR(255) NOT NULL DEFAULT 'ROLE_VIEWER',
    enabled BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_username (username),
    INDEX idx_user_email (email)
);

-- 초기 데모 데이터
INSERT INTO farms (farm_name, location) VALUES 
('스마트팜 A동', '경기도 화성시'),
('스마트팜 B동', '경기도 화성시');

INSERT INTO sensors (farm_id, sensor_type, sensor_name, location) VALUES 
(1, 'temperature', '온도센서-1', 'A동-구역1'),
(1, 'humidity', '습도센서-1', 'A동-구역1'),
(1, 'co2', 'CO2센서-1', 'A동-구역1'),
(2, 'temperature', '온도센서-2', 'B동-구역1'),
(2, 'humidity', '습도센서-2', 'B동-구역1');

-- 초기 사용자 데이터 (비밀번호: BCrypt 해시)
-- admin123, operator123, viewer123
INSERT INTO users (username, password_hash, email, full_name, roles) VALUES
('admin', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZRGdjGj/n3.rsR5HHqD0VRrrLKHhm', 'admin@terraneuron.io', 'System Admin', 'ROLE_ADMIN,ROLE_OPERATOR'),
('operator', '$2a$10$EblZqNptyYvcLm/VwDCVAuBjzZOI7khzdyGPBr08PpIi0na624b8.', 'operator@terraneuron.io', 'Farm Operator', 'ROLE_OPERATOR'),
('viewer', '$2a$10$LCi2jHTF8x/Q6qIH9mKNOOEq7ztEljW0oL1p.HPlVj.xrHHb9RYMW', 'viewer@terraneuron.io', 'Dashboard Viewer', 'ROLE_VIEWER');

-- ============================================================
-- Phase 4.E: 작물 모델링 (Crop Profile & Growth Stage)
-- ============================================================

-- 작물 프로필 테이블
CREATE TABLE IF NOT EXISTS crop_profiles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    crop_code VARCHAR(30) NOT NULL UNIQUE COMMENT '작물 코드 (tomato, lettuce, cucumber 등)',
    crop_name VARCHAR(100) NOT NULL COMMENT '작물명 (한글)',
    crop_name_en VARCHAR(100) NOT NULL COMMENT '작물명 (영문)',
    crop_family VARCHAR(50) COMMENT '작물 과 (가지과, 국화과 등)',
    description TEXT COMMENT '작물 설명',
    total_growth_days INT COMMENT '총 재배 기간 (일)',
    difficulty VARCHAR(20) DEFAULT 'MEDIUM' COMMENT '재배 난이도 (EASY, MEDIUM, HARD)',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_crop_code (crop_code),
    INDEX idx_crop_active (is_active)
);

-- 생장 단계별 최적 환경 조건 테이블
CREATE TABLE IF NOT EXISTS growth_stages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    crop_id BIGINT NOT NULL,
    stage_order INT NOT NULL COMMENT '단계 순서 (1=파종, 2=발아, ...)',
    stage_code VARCHAR(30) NOT NULL COMMENT '단계 코드 (seeding, germination, vegetative, flowering, fruiting, harvest)',
    stage_name VARCHAR(100) NOT NULL COMMENT '단계명 (한글)',
    duration_days INT NOT NULL COMMENT '해당 단계 기간 (일)',
    -- 온도 범위
    temp_min DECIMAL(4,1) NOT NULL COMMENT '최저 온도 (°C)',
    temp_optimal_low DECIMAL(4,1) NOT NULL COMMENT '최적 온도 하한 (°C)',
    temp_optimal_high DECIMAL(4,1) NOT NULL COMMENT '최적 온도 상한 (°C)',
    temp_max DECIMAL(4,1) NOT NULL COMMENT '최고 온도 (°C)',
    -- 습도 범위
    humidity_min DECIMAL(4,1) NOT NULL COMMENT '최저 습도 (%)',
    humidity_optimal_low DECIMAL(4,1) NOT NULL COMMENT '최적 습도 하한 (%)',
    humidity_optimal_high DECIMAL(4,1) NOT NULL COMMENT '최적 습도 상한 (%)',
    humidity_max DECIMAL(4,1) NOT NULL COMMENT '최고 습도 (%)',
    -- CO2 범위
    co2_min DECIMAL(6,1) DEFAULT 300 COMMENT '최저 CO2 (ppm)',
    co2_optimal DECIMAL(6,1) DEFAULT 800 COMMENT '최적 CO2 (ppm)',
    co2_max DECIMAL(6,1) DEFAULT 1200 COMMENT '최고 CO2 (ppm)',
    -- 광량
    light_min DECIMAL(7,1) DEFAULT 200 COMMENT '최저 광량 (lux)',
    light_optimal DECIMAL(7,1) DEFAULT 500 COMMENT '최적 광량 (lux)',
    light_max DECIMAL(7,1) DEFAULT 1000 COMMENT '최고 광량 (lux)',
    -- 토양 수분
    soil_moisture_min DECIMAL(4,1) DEFAULT 30 COMMENT '최저 토양 수분 (%)',
    soil_moisture_optimal DECIMAL(4,1) DEFAULT 60 COMMENT '최적 토양 수분 (%)',
    soil_moisture_max DECIMAL(4,1) DEFAULT 80 COMMENT '최고 토양 수분 (%)',
    -- 메모
    notes TEXT COMMENT '단계별 관리 주의사항',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crop_id) REFERENCES crop_profiles(id) ON DELETE CASCADE,
    UNIQUE KEY uk_crop_stage (crop_id, stage_order),
    INDEX idx_stage_crop (crop_id),
    INDEX idx_stage_code (stage_code)
);

-- 농장-작물 매핑 (어떤 농장에서 어떤 작물을 재배 중인지)
CREATE TABLE IF NOT EXISTS farm_crops (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_id VARCHAR(50) NOT NULL COMMENT '농장 ID',
    crop_id BIGINT NOT NULL,
    zone VARCHAR(50) COMMENT '재배 구역 (zone-A, zone-B 등)',
    planted_at DATE NOT NULL COMMENT '파종/정식일',
    current_stage_order INT DEFAULT 1 COMMENT '현재 생장 단계',
    expected_harvest DATE COMMENT '예상 수확일',
    status VARCHAR(20) DEFAULT 'GROWING' COMMENT 'GROWING, HARVESTED, TERMINATED',
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (crop_id) REFERENCES crop_profiles(id) ON DELETE CASCADE,
    INDEX idx_fc_farm (farm_id),
    INDEX idx_fc_status (status),
    INDEX idx_fc_crop (crop_id)
);

-- ============================================================
-- 작물 초기 데이터: 한국 스마트팜 주요 작물 5종
-- ============================================================

-- 1. 토마토
INSERT INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('tomato', '토마토', 'Tomato', '가지과', '한국 스마트팜 대표 작물. 온도와 일조량에 민감하며, 생장 단계별 환경 관리가 중요.', 150, 'MEDIUM');

INSERT INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 1, 'seeding', '파종/육묘', 25,
    20.0, 23.0, 28.0, 32.0, 60.0, 70.0, 80.0, 90.0, 400, 800, 1200, 300, 500, 800, 60, 70, 80,
    '균일한 온도 유지 필수. 야간 온도 18°C 이상.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 2, 'vegetative', '영양생장', 30,
    18.0, 22.0, 26.0, 30.0, 55.0, 65.0, 75.0, 85.0, 400, 1000, 1500, 400, 600, 1000, 55, 65, 75,
    '충분한 광량 확보. 질소 시비 중요.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 3, 'flowering', '개화기', 20,
    16.0, 20.0, 25.0, 28.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 500, 700, 1000, 50, 60, 70,
    '과도한 습도는 수분 불량 유발. 야간 15-17°C 유지.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 4, 'fruiting', '착과/비대기', 50,
    15.0, 20.0, 26.0, 30.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 500, 700, 1000, 50, 65, 75,
    '칼륨 시비 강화. 일교차 8-10°C로 착색 촉진.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 5, 'harvest', '수확기', 25,
    14.0, 18.0, 24.0, 28.0, 50.0, 55.0, 65.0, 75.0, 300, 600, 1000, 400, 600, 800, 45, 55, 65,
    '과숙 방지를 위해 온도 관리. 수확 후 낮은 습도 유지.');

-- 2. 딸기
INSERT INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('strawberry', '딸기', 'Strawberry', '장미과', '고부가가치 작물. 일장과 온도에 의한 화아분화 관리가 핵심.', 180, 'HARD');

INSERT INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 1, 'planting', '정식기', 20,
    15.0, 18.0, 23.0, 28.0, 60.0, 70.0, 80.0, 90.0, 300, 600, 1000, 200, 400, 600, 60, 70, 80,
    '활착 기간 충분한 수분 공급. 차광 관리.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 2, 'vegetative', '영양생장', 40,
    12.0, 15.0, 20.0, 25.0, 55.0, 65.0, 75.0, 85.0, 300, 800, 1200, 300, 500, 800, 55, 65, 75,
    '화아분화 유도를 위해 야간 온도 관리.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 3, 'flowering', '개화기', 30,
    8.0, 12.0, 18.0, 22.0, 50.0, 55.0, 65.0, 75.0, 400, 1000, 1500, 400, 600, 1000, 50, 60, 70,
    '수분 매개 관리. 과습 방지 중요.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 4, 'fruiting', '착과/비대기', 60,
    8.0, 13.0, 20.0, 25.0, 50.0, 55.0, 65.0, 75.0, 400, 1000, 1500, 500, 700, 1000, 45, 55, 65,
    '당도 향상을 위해 일교차 관리. 칼슘 시비.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 5, 'harvest', '수확기', 30,
    5.0, 10.0, 18.0, 23.0, 45.0, 50.0, 60.0, 70.0, 300, 600, 1000, 400, 600, 800, 40, 50, 60,
    '잿빛곰팡이 주의. 수확 후 저온 보관.');

-- 3. 상추
INSERT INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('lettuce', '상추', 'Lettuce', '국화과', '빠른 생육 주기의 엽채류. 고온에서 추대하므로 온도 관리 핵심.', 45, 'EASY');

INSERT INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 1, 'seeding', '파종/육묘', 10,
    15.0, 18.0, 22.0, 25.0, 65.0, 70.0, 80.0, 90.0, 300, 600, 1000, 200, 400, 600, 65, 75, 85,
    '발아 적온 18-20°C. 광발아 종자.'),
((SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 2, 'vegetative', '본엽 생장', 25,
    10.0, 15.0, 20.0, 25.0, 55.0, 60.0, 70.0, 80.0, 400, 800, 1200, 300, 500, 800, 55, 65, 75,
    '25°C 이상 고온 시 추대 위험. 차광 필요할 수 있음.'),
((SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 3, 'harvest', '수확기', 10,
    10.0, 15.0, 20.0, 24.0, 50.0, 55.0, 65.0, 75.0, 300, 600, 1000, 300, 500, 700, 50, 60, 70,
    '수확 2-3일 전 관수 줄여 저장성 향상.');

-- 4. 오이
INSERT INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('cucumber', '오이', 'Cucumber', '박과', '고온성 작물로 자람이 빠름. 과습에 강하지만 과건에 약함.', 90, 'MEDIUM');

INSERT INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 1, 'seeding', '파종/육묘', 15,
    22.0, 25.0, 28.0, 32.0, 65.0, 75.0, 85.0, 95.0, 300, 600, 1000, 200, 400, 700, 65, 75, 85,
    '발아 적온 25-28°C. 고온 필수.'),
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 2, 'vegetative', '덩굴 생장', 25,
    18.0, 22.0, 28.0, 32.0, 60.0, 70.0, 80.0, 90.0, 400, 1000, 1500, 400, 600, 1000, 60, 70, 80,
    '충분한 수분과 질소 공급. 유인 작업.'),
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 3, 'flowering', '개화/착과', 15,
    16.0, 20.0, 26.0, 30.0, 55.0, 65.0, 75.0, 85.0, 400, 1000, 1500, 500, 700, 1000, 55, 65, 75,
    '주간/야간 온도차 관리. 암꽃 착생 촉진.'),
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 4, 'harvest', '수확기', 35,
    15.0, 20.0, 26.0, 30.0, 55.0, 60.0, 70.0, 80.0, 400, 800, 1200, 400, 600, 800, 55, 65, 75,
    '연속 수확 기간. 적엽/적과로 수세 유지.');

-- 5. 파프리카
INSERT INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('paprika', '파프리카', 'Paprika (Bell Pepper)', '가지과', '고부가가치 수출 작물. 정밀 환경제어 필요.', 180, 'HARD');

INSERT INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 1, 'seeding', '파종/육묘', 30,
    22.0, 25.0, 28.0, 32.0, 65.0, 70.0, 80.0, 90.0, 400, 800, 1200, 300, 500, 800, 60, 70, 80,
    '발아 적온 25-30°C. 야간 20°C 이상 유지.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 2, 'vegetative', '영양생장', 40,
    18.0, 22.0, 26.0, 30.0, 55.0, 65.0, 75.0, 85.0, 400, 1000, 1500, 500, 700, 1000, 55, 65, 75,
    '강한 줄기 형성을 위한 광량/CO2 관리.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 3, 'flowering', '개화기', 25,
    16.0, 20.0, 25.0, 28.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 600, 800, 1200, 50, 60, 70,
    '야간 16-18°C로 화아분화 촉진. 붕소 엽면시비.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 4, 'fruiting', '착과/비대기', 55,
    16.0, 20.0, 26.0, 30.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 600, 800, 1200, 50, 60, 70,
    '칼슘/칼륨 시비 강화. 열과 방지 환기.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 5, 'harvest', '수확/착색기', 30,
    14.0, 18.0, 24.0, 28.0, 45.0, 55.0, 65.0, 75.0, 300, 600, 1000, 500, 700, 1000, 45, 55, 65,
    '착색을 위해 일교차 10°C 이상 확보.');

-- 데모 농장-작물 매핑
INSERT INTO farm_crops (farm_id, crop_id, zone, planted_at, current_stage_order, expected_harvest, status) VALUES
('farm-A', (SELECT id FROM crop_profiles WHERE crop_code='tomato'), 'zone-A', '2026-01-15', 3, '2026-06-15', 'GROWING'),
('farm-A', (SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 'zone-B', '2026-02-10', 2, '2026-03-27', 'GROWING'),
('farm-B', (SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 'zone-A', '2025-10-01', 4, '2026-03-30', 'GROWING');

