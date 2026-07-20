CREATE TABLE IF NOT EXISTS refresh_token_sessions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    token_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    username VARCHAR(50) NOT NULL,
    family_id VARCHAR(36) NOT NULL,
    issued_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6),
    revoke_reason VARCHAR(50),
    replaced_by_token_id VARCHAR(36),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_refresh_token_id UNIQUE (token_id),
    CONSTRAINT uk_refresh_token_hash UNIQUE (token_hash),
    INDEX idx_refresh_username (username),
    INDEX idx_refresh_family (family_id),
    INDEX idx_refresh_expires_at (expires_at)
) ENGINE=InnoDB;
