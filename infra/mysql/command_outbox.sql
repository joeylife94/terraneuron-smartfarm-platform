USE terra_ops;

CREATE TABLE IF NOT EXISTS command_outbox (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL UNIQUE,
    plan_id VARCHAR(50) NOT NULL,
    command_id VARCHAR(50) NOT NULL UNIQUE,
    topic VARCHAR(100) NOT NULL,
    message_key VARCHAR(100) NOT NULL,
    payload LONGTEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMP(6) NOT NULL,
    locked_at TIMESTAMP(6) NULL,
    published_at TIMESTAMP(6) NULL,
    last_error TEXT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_outbox_status_due (status, next_attempt_at),
    INDEX idx_outbox_plan_id (plan_id),
    INDEX idx_outbox_locked_at (locked_at)
);
