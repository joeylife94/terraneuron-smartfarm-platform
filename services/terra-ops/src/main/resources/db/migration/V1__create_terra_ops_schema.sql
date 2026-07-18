-- Canonical Terra-Ops schema. This migration is safe to run after baseline 0:
-- existing tables are preserved and V2 reconciles legacy action-plan columns.

CREATE TABLE IF NOT EXISTS farms (
    farm_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_name VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_id BIGINT NOT NULL,
    sensor_type VARCHAR(50) NOT NULL,
    sensor_name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_sensor_farm FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS insights (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id VARCHAR(100),
    farm_id VARCHAR(255) NOT NULL,
    asset_id VARCHAR(100),
    asset_type VARCHAR(50),
    sensor_type VARCHAR(50),
    status VARCHAR(50) NOT NULL,
    severity VARCHAR(50),
    message TEXT,
    raw_value FLOAT(53),
    confidence FLOAT(53),
    llm_recommendation TEXT,
    rag_context TEXT,
    timestamp DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_farm_id (farm_id),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    insight_id BIGINT NOT NULL,
    alert_status VARCHAR(20) DEFAULT 'PENDING',
    sent_at DATETIME(6),
    acknowledged_at DATETIME(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_alert_insight FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS action_plans (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    plan_id VARCHAR(50) NOT NULL,
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
    requires_approval BIT DEFAULT b'1',
    approved_by VARCHAR(100),
    approved_at DATETIME(6),
    rejection_reason TEXT,
    command_id VARCHAR(50),
    dispatched_at DATETIME(6),
    delivered_at DATETIME(6),
    ack_deadline_at DATETIME(6),
    executed_at DATETIME(6),
    execution_result VARCHAR(50),
    execution_error TEXT,
    generated_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_action_plan_id UNIQUE (plan_id),
    INDEX idx_plan_farm_id (farm_id),
    INDEX idx_plan_status (status),
    INDEX idx_plan_trace_id (trace_id),
    INDEX idx_plan_priority (priority),
    INDEX idx_plan_expires_at (expires_at),
    INDEX idx_plan_command_id (command_id),
    INDEX idx_plan_ack_deadline (ack_deadline_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_id VARCHAR(50) NOT NULL,
    trace_id VARCHAR(100) NOT NULL,
    log_type VARCHAR(30) DEFAULT 'activity',
    event_type VARCHAR(30) NOT NULL,
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(50) NOT NULL,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(255) NOT NULL,
    details JSON,
    timestamp DATETIME(6) NOT NULL,
    success BIT NOT NULL DEFAULT b'1',
    error_message TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_audit_log_id UNIQUE (log_id),
    INDEX idx_audit_trace_id (trace_id),
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_event_type (event_type),
    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_actor (actor)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    full_name VARCHAR(100),
    roles VARCHAR(255) NOT NULL DEFAULT 'ROLE_VIEWER',
    enabled BIT NOT NULL DEFAULT b'1',
    last_login DATETIME(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE INDEX idx_user_username (username),
    INDEX idx_user_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS crop_profiles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    crop_code VARCHAR(30) NOT NULL,
    crop_name VARCHAR(100) NOT NULL,
    crop_name_en VARCHAR(100) NOT NULL,
    crop_family VARCHAR(50),
    description TEXT,
    total_growth_days INT,
    difficulty VARCHAR(20) DEFAULT 'MEDIUM',
    is_active BIT DEFAULT b'1',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE INDEX idx_crop_code (crop_code),
    INDEX idx_crop_active (is_active)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS growth_stages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    crop_id BIGINT NOT NULL,
    stage_order INT NOT NULL,
    stage_code VARCHAR(30) NOT NULL,
    stage_name VARCHAR(100) NOT NULL,
    duration_days INT NOT NULL,
    temp_min FLOAT(53) NOT NULL,
    temp_optimal_low FLOAT(53) NOT NULL,
    temp_optimal_high FLOAT(53) NOT NULL,
    temp_max FLOAT(53) NOT NULL,
    humidity_min FLOAT(53) NOT NULL,
    humidity_optimal_low FLOAT(53) NOT NULL,
    humidity_optimal_high FLOAT(53) NOT NULL,
    humidity_max FLOAT(53) NOT NULL,
    co2_min FLOAT(53) DEFAULT 300,
    co2_optimal FLOAT(53) DEFAULT 800,
    co2_max FLOAT(53) DEFAULT 1200,
    light_min FLOAT(53) DEFAULT 200,
    light_optimal FLOAT(53) DEFAULT 500,
    light_max FLOAT(53) DEFAULT 1000,
    soil_moisture_min FLOAT(53) DEFAULT 30,
    soil_moisture_optimal FLOAT(53) DEFAULT 60,
    soil_moisture_max FLOAT(53) DEFAULT 80,
    notes TEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_growth_stage_crop FOREIGN KEY (crop_id) REFERENCES crop_profiles(id) ON DELETE CASCADE,
    CONSTRAINT uk_crop_stage UNIQUE (crop_id, stage_order),
    INDEX idx_stage_crop (crop_id),
    INDEX idx_stage_code (stage_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS farm_crops (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_id VARCHAR(50) NOT NULL,
    crop_id BIGINT NOT NULL,
    zone VARCHAR(50),
    planted_at DATE NOT NULL,
    current_stage_order INT DEFAULT 1,
    expected_harvest DATE,
    status VARCHAR(20) DEFAULT 'GROWING',
    notes TEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_farm_crop_profile FOREIGN KEY (crop_id) REFERENCES crop_profiles(id) ON DELETE CASCADE,
    INDEX idx_fc_farm (farm_id),
    INDEX idx_fc_status (status),
    INDEX idx_fc_crop (crop_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS command_outbox (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL,
    plan_id VARCHAR(50) NOT NULL,
    command_id VARCHAR(50) NOT NULL,
    topic VARCHAR(100) NOT NULL,
    message_key VARCHAR(100) NOT NULL,
    payload LONGTEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at DATETIME(6) NOT NULL,
    locked_at DATETIME(6),
    published_at DATETIME(6),
    last_error TEXT,
    version BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT uk_outbox_event_id UNIQUE (event_id),
    CONSTRAINT uk_outbox_command_id UNIQUE (command_id),
    INDEX idx_outbox_status_due (status, next_attempt_at),
    INDEX idx_outbox_plan_id (plan_id),
    INDEX idx_outbox_locked_at (locked_at)
) ENGINE=InnoDB;
