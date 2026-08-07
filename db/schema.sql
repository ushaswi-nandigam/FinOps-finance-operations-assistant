-- Agentic FinOps Assistant — MySQL 8 schema
-- Applied by scripts/migrate.py (`make migrate`). One file, no migration framework —
-- simple to read and simple for a judge to run. InnoDB + utf8mb4 throughout.

CREATE DATABASE IF NOT EXISTS finops_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE finops_db;

SET NAMES utf8mb4;

-- =====================================================================
-- Reference / mock-enterprise-system data (backs mock-crm, mock-payments,
-- mock-casemgmt, mock-kb)
-- =====================================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_ref     VARCHAR(64)  PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,
    email             VARCHAR(255) NOT NULL,
    phone             VARCHAR(32)  NOT NULL,
    tier              ENUM('STANDARD','SILVER','GOLD','PLATINUM') NOT NULL DEFAULT 'STANDARD',
    tenure_months     INT NOT NULL DEFAULT 0,
    kyc_status        ENUM('VERIFIED','PENDING','REJECTED') NOT NULL DEFAULT 'PENDING',
    is_flagged        BOOLEAN NOT NULL DEFAULT FALSE,
    is_minor          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        DATETIME NOT NULL,
    INDEX idx_customers_flagged (is_flagged)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transactions (
    txn_id            VARCHAR(64) PRIMARY KEY,
    customer_ref      VARCHAR(64) NOT NULL,
    amount_inr        DECIMAL(12,2) NOT NULL,
    currency          VARCHAR(8) NOT NULL DEFAULT 'INR',
    merchant_category VARCHAR(32) NOT NULL,
    status            ENUM('SUCCESS','FAILED','REFUNDED','PARTIALLY_REFUNDED') NOT NULL DEFAULT 'SUCCESS',
    decline_code      VARCHAR(32) NOT NULL DEFAULT 'NONE',
    is_fraud_labeled  BOOLEAN NOT NULL DEFAULT FALSE,
    device_id         VARCHAR(64) NOT NULL,
    ip_address        VARCHAR(45) NOT NULL,
    timestamp         DATETIME NOT NULL,
    FOREIGN KEY (customer_ref) REFERENCES customers(customer_ref),
    INDEX idx_txn_customer (customer_ref),
    INDEX idx_txn_status (status),
    INDEX idx_txn_device (device_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id         VARCHAR(64) PRIMARY KEY,
    customer_ref      VARCHAR(64) NOT NULL,
    intent            VARCHAR(64) NOT NULL,
    text              TEXT NOT NULL,
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (customer_ref) REFERENCES customers(customer_ref),
    INDEX idx_tickets_customer (customer_ref)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id     VARCHAR(64) PRIMARY KEY,
    customer_ref      VARCHAR(64) NOT NULL,
    channel           ENUM('chat','call') NOT NULL,
    turns             JSON NOT NULL,
    contains_pii      BOOLEAN NOT NULL DEFAULT FALSE,
    contains_injection BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (customer_ref) REFERENCES customers(customer_ref)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS disputes (
    dispute_id        VARCHAR(64) PRIMARY KEY,
    customer_ref      VARCHAR(64) NOT NULL,
    txn_id            VARCHAR(64) NOT NULL,
    reason            VARCHAR(128) NOT NULL,
    amount_inr        DECIMAL(12,2) NOT NULL,
    lifecycle_stage   ENUM('FILED','UNDER_REVIEW','MERCHANT_RESPONDED','REPRESENTED','RESOLVED_CUSTOMER','RESOLVED_MERCHANT') NOT NULL DEFAULT 'FILED',
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (customer_ref) REFERENCES customers(customer_ref),
    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fraud_cases (
    fraud_case_id     VARCHAR(64) PRIMARY KEY,
    customer_ref      VARCHAR(64) NOT NULL,
    txn_id            VARCHAR(64) NOT NULL,
    status            ENUM('OPEN','INVESTIGATING','CLOSED_FRAUD','CLOSED_BENIGN') NOT NULL DEFAULT 'OPEN',
    risk_score        FLOAT NOT NULL DEFAULT 0,
    linked_accounts   JSON NOT NULL,
    investigator_notes TEXT NOT NULL,
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (customer_ref) REFERENCES customers(customer_ref),
    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS policies (
    id                VARCHAR(32) PRIMARY KEY,
    title             VARCHAR(255) NOT NULL,
    content           TEXT NOT NULL,
    category          VARCHAR(64) NOT NULL DEFAULT 'general'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS policy_embeddings (
    policy_id         VARCHAR(32) PRIMARY KEY,
    embedding         JSON NOT NULL,
    model_name        VARCHAR(64) NOT NULL,
    FOREIGN KEY (policy_id) REFERENCES policies(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sops (
    id                VARCHAR(32) PRIMARY KEY,
    title             VARCHAR(255) NOT NULL,
    content           TEXT NOT NULL,
    category          VARCHAR(64) NOT NULL DEFAULT 'general'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS internal_ops_workflows (
    workflow_id       VARCHAR(64) PRIMARY KEY,
    title             VARCHAR(255) NOT NULL,
    description       TEXT NOT NULL,
    category          VARCHAR(64) NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    status            ENUM('OPEN','IN_PROGRESS','APPROVED','REJECTED','DONE') NOT NULL DEFAULT 'OPEN',
    created_at        DATETIME NOT NULL
) ENGINE=InnoDB;

-- =====================================================================
-- L1-L2: ingress, normalisation, PII vault
-- =====================================================================

CREATE TABLE IF NOT EXISTS raw_events (
    event_id          VARCHAR(64) PRIMARY KEY,
    source            VARCHAR(64) NOT NULL,
    payload           JSON NOT NULL,
    received_at       DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ops_events (
    event_id          VARCHAR(64) PRIMARY KEY,
    source            VARCHAR(64) NOT NULL,
    received_at       DATETIME NOT NULL,
    customer_ref      VARCHAR(64) NOT NULL,
    channel           VARCHAR(32) NOT NULL,
    redacted_text     TEXT NOT NULL,
    entities          JSON NOT NULL,
    attachments       JSON NOT NULL,
    trace_id          VARCHAR(64) NOT NULL,
    processed_l2      BOOLEAN NOT NULL DEFAULT FALSE,
    INDEX idx_ops_events_customer (customer_ref)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pii_vault (
    token             VARCHAR(64) PRIMARY KEY,
    field_type        VARCHAR(32) NOT NULL,
    encrypted_value   TEXT NOT NULL,
    created_at        DATETIME NOT NULL
) ENGINE=InnoDB;

-- =====================================================================
-- L4: case state machine (checkpointed after every transition)
-- =====================================================================

CREATE TABLE IF NOT EXISTS cases (
    case_id           VARCHAR(64) PRIMARY KEY,
    event_id          VARCHAR(64) NOT NULL,
    domain            ENUM('support','payments','fraud','internal_ops','compliance') NOT NULL,
    status            VARCHAR(32) NOT NULL DEFAULT 'INTAKE',
    customer_ref      VARCHAR(64) NOT NULL,
    plan              JSON NOT NULL,
    observations      JSON NOT NULL,
    proposals         JSON NOT NULL,
    verifier_report   JSON NOT NULL,
    risk_decision     JSON NOT NULL,
    cost_tokens_in    INT NOT NULL DEFAULT 0,
    cost_tokens_out   INT NOT NULL DEFAULT 0,
    cost_inr          DECIMAL(10,4) NOT NULL DEFAULT 0,
    cost_budget_inr   DECIMAL(10,4) NOT NULL DEFAULT 5.0,
    tool_calls_used   INT NOT NULL DEFAULT 0,
    max_tool_calls    INT NOT NULL DEFAULT 6,
    revisions         INT NOT NULL DEFAULT 0,
    max_revisions     INT NOT NULL DEFAULT 3,
    triage_stage      VARCHAR(16) DEFAULT NULL,
    error             TEXT DEFAULT NULL,
    created_at        DATETIME NOT NULL,
    updated_at        DATETIME NOT NULL,
    INDEX idx_cases_status (status),
    INDEX idx_cases_domain (domain),
    INDEX idx_cases_customer (customer_ref)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS action_proposals (
    proposal_id       VARCHAR(64) PRIMARY KEY,
    case_id           VARCHAR(64) NOT NULL,
    domain            VARCHAR(32) NOT NULL,
    action_type       VARCHAR(64) NOT NULL,
    args              JSON NOT NULL,
    evidence          JSON NOT NULL,
    confidence        FLOAT NOT NULL,
    proposed_by       VARCHAR(64) NOT NULL,
    reasoning         TEXT NOT NULL,
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    INDEX idx_proposals_case (case_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS risk_decisions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    proposal_id       VARCHAR(64) NOT NULL,
    case_id           VARCHAR(64) NOT NULL,
    tier              ENUM('T0','T1','T2','T3') NOT NULL,
    outcome           ENUM('AUTO_EXECUTE','NEEDS_APPROVAL','DUAL_APPROVAL','ESCALATE','DENY') NOT NULL,
    matched_rules     JSON NOT NULL,
    reason_plain      TEXT NOT NULL,
    policy_version    VARCHAR(16) NOT NULL,
    required_approvers INT NOT NULL DEFAULT 0,
    requires_distinct_approvers BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    INDEX idx_risk_decisions_proposal (proposal_id)
) ENGINE=InnoDB;

-- =====================================================================
-- L8: human-in-the-loop approvals (maker != checker enforced below)
-- =====================================================================

CREATE TABLE IF NOT EXISTS approvals (
    approval_id       VARCHAR(64) PRIMARY KEY,
    case_id           VARCHAR(64) NOT NULL,
    proposal_id       VARCHAR(64) NOT NULL,
    slot_no           INT NOT NULL DEFAULT 1,          -- 1 or 2 for dual approval
    status            ENUM('PENDING','APPROVED','REJECTED','MODIFIED','SENT_BACK','EXPIRED') NOT NULL DEFAULT 'PENDING',
    approver_id       VARCHAR(64) DEFAULT NULL,
    decision_reason   TEXT DEFAULT NULL,
    sla_deadline      DATETIME NOT NULL,
    decided_at        DATETIME DEFAULT NULL,
    created_at        DATETIME NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    UNIQUE KEY uq_proposal_approver (proposal_id, approver_id),
    INDEX idx_approvals_status (status)
) ENGINE=InnoDB;

-- =====================================================================
-- L9: execution — idempotency
-- =====================================================================

CREATE TABLE IF NOT EXISTS tool_calls (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    case_id           VARCHAR(64) NOT NULL,
    tool_name         VARCHAR(64) NOT NULL,
    idempotency_key   VARCHAR(128) NOT NULL,
    args              JSON NOT NULL,
    dry_run           BOOLEAN NOT NULL DEFAULT FALSE,
    status            ENUM('DRY_RUN','SUCCESS','FAILED','ROLLED_BACK') NOT NULL DEFAULT 'SUCCESS',
    result            JSON NOT NULL,
    created_at        DATETIME NOT NULL,
    UNIQUE KEY uq_idempotency_key (idempotency_key),
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;

-- =====================================================================
-- L10: audit ledger — append-only, hash-chained (global chain)
-- =====================================================================

CREATE TABLE IF NOT EXISTS decision_records (
    seq               INT AUTO_INCREMENT PRIMARY KEY,   -- global chain position
    decision_id       VARCHAR(64) NOT NULL UNIQUE,
    case_id           VARCHAR(64) NOT NULL,
    case_seq          INT NOT NULL,                      -- position within the case
    timestamp         DATETIME(6) NOT NULL,               -- microsecond precision: the hash chain is computed
                                                            -- over this value, and MySQL's default DATETIME
                                                            -- truncates microseconds and drops tzinfo, which
                                                            -- would make every recomputed hash mismatch
    actor_type        VARCHAR(16) NOT NULL,
    actor_name        VARCHAR(64) NOT NULL,
    actor_model       VARCHAR(64) DEFAULT NULL,
    actor_version     VARCHAR(16) DEFAULT NULL,
    action            JSON NOT NULL,
    outcome           VARCHAR(32) NOT NULL,
    reason_plain      TEXT NOT NULL,
    evidence          JSON NOT NULL,
    matched_rules     JSON NOT NULL,
    verifier          JSON NOT NULL,
    cost_stage        VARCHAR(16) NOT NULL,
    cost_tokens_in    INT NOT NULL DEFAULT 0,
    cost_tokens_out   INT NOT NULL DEFAULT 0,
    cost_inr          DECIMAL(10,4) NOT NULL DEFAULT 0,
    policy_version    VARCHAR(16) NOT NULL,
    prev_hash         CHAR(64) NOT NULL,
    entry_hash        CHAR(64) NOT NULL,
    INDEX idx_decision_records_case (case_id)
) ENGINE=InnoDB;

-- =====================================================================
-- Auth / RBAC
-- =====================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id           VARCHAR(64) PRIMARY KEY,
    username          VARCHAR(64) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,
    role              ENUM('viewer','ops_agent','approver','supervisor','auditor') NOT NULL DEFAULT 'viewer',
    created_at        DATETIME NOT NULL
) ENGINE=InnoDB;
