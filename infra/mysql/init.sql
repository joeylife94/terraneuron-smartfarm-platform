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

