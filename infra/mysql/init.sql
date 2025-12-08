-- TerraNeuron 운영 통제 서비스 초기 스키마
-- terra-ops 서비스용 MySQL 데이터베이스

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
