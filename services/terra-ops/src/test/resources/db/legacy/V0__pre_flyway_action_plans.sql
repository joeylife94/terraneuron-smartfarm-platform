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

INSERT INTO action_plans (
    plan_id, trace_id, farm_id, target_asset_id, action_category, action_type,
    status, priority, generated_at
) VALUES (
    'legacy-plan-preserved', 'trace-legacy', 'farm-legacy', 'fan-legacy',
    'ventilation', 'turn_on', 'PENDING', 'MEDIUM', CURRENT_TIMESTAMP
);
