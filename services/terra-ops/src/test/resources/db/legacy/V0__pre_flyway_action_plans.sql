CREATE TABLE action_plans (
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
    status ENUM(
        'PENDING', 'APPROVED', 'DISPATCHING', 'DISPATCHED', 'DELIVERED',
        'EXECUTED', 'REJECTED', 'DISPATCH_FAILED', 'DELIVERY_FAILED',
        'EXECUTION_FAILED', 'ACK_TIMEOUT', 'FAILED', 'EXPIRED', 'CANCELLED'
    ) NOT NULL DEFAULT 'PENDING',
    priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'MEDIUM',
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

INSERT INTO action_plans (
    plan_id, trace_id, farm_id, target_asset_id, action_category, action_type,
    status, priority, generated_at
) VALUES (
    'legacy-plan-preserved', 'trace-legacy', 'farm-legacy', 'fan-legacy',
    'ventilation', 'turn_on', 'APPROVED', 'HIGH', CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_id VARCHAR(50) NOT NULL,
    trace_id VARCHAR(100) NOT NULL,
    log_type VARCHAR(30) DEFAULT 'activity',
    event_type ENUM(
        'PLAN_CREATED', 'PLAN_VALIDATED', 'PLAN_APPROVED', 'PLAN_REJECTED',
        'PLAN_EXPIRED', 'PLAN_CANCELLED', 'COMMAND_QUEUED', 'COMMAND_EXECUTED',
        'COMMAND_FAILED', 'COMMAND_TIMEOUT', 'ALERT_TRIGGERED',
        'ALERT_ACKNOWLEDGED', 'ALERT_RESOLVED', 'ALERT_ESCALATED',
        'INSIGHT_DETECTED', 'INSIGHT_PROCESSED', 'SYSTEM_ERROR',
        'SECURITY_VIOLATION', 'CONFIG_CHANGED'
    ) NOT NULL,
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
);

INSERT INTO audit_logs (
    log_id, trace_id, event_type, entity_type, entity_id, actor, action, timestamp
) VALUES (
    'legacy-log-preserved', 'trace-legacy', 'PLAN_CREATED', 'plan',
    'legacy-plan-preserved', 'system', 'created legacy plan', CURRENT_TIMESTAMP(6)
);

CREATE TABLE command_outbox (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL,
    plan_id VARCHAR(50) NOT NULL,
    command_id VARCHAR(50) NOT NULL,
    topic VARCHAR(100) NOT NULL,
    message_key VARCHAR(100) NOT NULL,
    payload LONGTEXT NOT NULL,
    status ENUM('PENDING', 'PROCESSING', 'PUBLISHED', 'DEAD') NOT NULL DEFAULT 'PENDING',
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
);

-- The pre-safety schema allowed multiple commands for one plan. V4 must
-- preserve the most advanced lifecycle truth and archive the other rows.
INSERT INTO command_outbox (
    event_id, plan_id, command_id, topic, message_key, payload, status,
    attempts, next_attempt_at, created_at, updated_at
) VALUES
(
    '00000000-0000-0000-0000-000000000001',
    'legacy-plan-preserved',
    'legacy-command-preserved',
    'terra.control.command',
    'legacy-command-preserved',
    '{}',
    'PUBLISHED',
    1,
    CURRENT_TIMESTAMP(6),
    CURRENT_TIMESTAMP(6),
    CURRENT_TIMESTAMP(6)
),
(
    '00000000-0000-0000-0000-000000000002',
    'legacy-plan-preserved',
    'legacy-command-processing',
    'terra.control.command',
    'legacy-command-processing',
    '{}',
    'PROCESSING',
    1,
    CURRENT_TIMESTAMP(6),
    CURRENT_TIMESTAMP(6),
    CURRENT_TIMESTAMP(6)
),
(
    '00000000-0000-0000-0000-000000000003',
    'legacy-plan-preserved',
    'legacy-command-pending',
    'terra.control.command',
    'legacy-command-pending',
    '{}',
    'PENDING',
    0,
    CURRENT_TIMESTAMP(6),
    CURRENT_TIMESTAMP(6),
    CURRENT_TIMESTAMP(6)
);
