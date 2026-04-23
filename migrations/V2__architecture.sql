-- V2 Architecture schema for Neon PostgreSQL
-- NOTE: Documentation migration; review/apply in a Neon dev branch first.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Strategies
CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    spec JSONB NOT NULL,
    model_id UUID,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',

    validation_result JSONB,
    feedback_payload JSONB,
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN (
        'draft', 'backtest_pending', 'backtest_running', 'validation_pending',
        'approved', 'rejected', 'warning', 'deployed', 'archived', 'human_review'
    ))
);

CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status);
CREATE INDEX IF NOT EXISTS idx_strategies_model_id ON strategies(model_id);

-- Models
CREATE TABLE IF NOT EXISTS models_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategies(id),
    architecture VARCHAR(100),
    hyperparams JSONB,

    directional_accuracy DECIMAL(5,4),
    r2_score DECIMAL(5,4),
    mse DECIMAL(15,10),
    train_test_gap DECIMAL(5,4),

    artifact_path VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'training',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    validated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_models_v2_strategy_id ON models_v2(strategy_id);
CREATE INDEX IF NOT EXISTS idx_models_v2_status ON models_v2(status);

-- Bind strategies.model_id after models_v2 exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_strategies_model'
    ) THEN
        ALTER TABLE strategies
            ADD CONSTRAINT fk_strategies_model
            FOREIGN KEY (model_id) REFERENCES models_v2(id);
    END IF;
END $$;

-- Backtest reports
CREATE TABLE IF NOT EXISTS backtest_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategies(id),
    method VARCHAR(50) NOT NULL,

    sharpe_ratio DECIMAL(5,4),
    sortino_ratio DECIMAL(5,4),
    cagr DECIMAL(8,4),
    total_return DECIMAL(8,4),
    max_drawdown DECIMAL(5,4),
    max_drawdown_duration INT,
    profit_factor DECIMAL(5,4),
    win_rate DECIMAL(5,4),
    avg_trade_return DECIMAL(8,6),

    var_95 DECIMAL(8,6),
    cvar_95 DECIMAL(8,6),
    kelly_fraction DECIMAL(5,4),
    risk_of_ruin DECIMAL(5,4),

    monte_carlo_pvalue DECIMAL(5,4),
    regime_stability_score DECIMAL(5,4),

    equity_curve JSONB,
    trades JSONB,
    params JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_reports_strategy_id ON backtest_reports(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_reports_method ON backtest_reports(method);

-- Validations
CREATE TABLE IF NOT EXISTS validations_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategies(id),
    backtest_report_id UUID REFERENCES backtest_reports(id),

    level VARCHAR(5) NOT NULL,
    status VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50),
    expected_threshold VARCHAR(50),
    actual_value DECIMAL(10,6),
    details TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validations_v2_strategy_id ON validations_v2(strategy_id);
CREATE INDEX IF NOT EXISTS idx_validations_v2_status ON validations_v2(status);

-- Trigger helper
CREATE OR REPLACE FUNCTION publish_event(payload JSONB)
RETURNS VOID AS $$
BEGIN
    PERFORM pg_notify('events', payload::text);
END;
$$ LANGUAGE plpgsql;

-- spec.created
CREATE OR REPLACE FUNCTION notify_spec_created()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM publish_event(jsonb_build_object(
        'event', 'spec.created',
        'strategy_id', NEW.id,
        'timestamp', NOW()
    ));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_spec_created ON strategies;
CREATE TRIGGER trg_spec_created
AFTER INSERT ON strategies
FOR EACH ROW
EXECUTE FUNCTION notify_spec_created();

-- model.validated / model.rejected
CREATE OR REPLACE FUNCTION notify_model_state_changed()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'validated' AND COALESCE(OLD.status, '') <> 'validated' THEN
        PERFORM publish_event(jsonb_build_object(
            'event', 'model.validated',
            'model_id', NEW.id,
            'strategy_id', NEW.strategy_id,
            'timestamp', NOW()
        ));
    ELSIF NEW.status = 'rejected' AND COALESCE(OLD.status, '') <> 'rejected' THEN
        PERFORM publish_event(jsonb_build_object(
            'event', 'model.rejected',
            'model_id', NEW.id,
            'strategy_id', NEW.strategy_id,
            'timestamp', NOW()
        ));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_model_state_changed ON models_v2;
CREATE TRIGGER trg_model_state_changed
AFTER UPDATE ON models_v2
FOR EACH ROW
EXECUTE FUNCTION notify_model_state_changed();

-- backtest.completed
CREATE OR REPLACE FUNCTION notify_backtest_completed()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM publish_event(jsonb_build_object(
        'event', 'backtest.completed',
        'report_id', NEW.id,
        'strategy_id', NEW.strategy_id,
        'method', NEW.method,
        'timestamp', NOW()
    ));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_backtest_completed ON backtest_reports;
CREATE TRIGGER trg_backtest_completed
AFTER INSERT ON backtest_reports
FOR EACH ROW
EXECUTE FUNCTION notify_backtest_completed();

-- validation branching
CREATE OR REPLACE FUNCTION handle_validation_result()
RETURNS TRIGGER AS $$
DECLARE
    v_retry_count INT;
    v_max_retries INT;
BEGIN
    SELECT retry_count, max_retries
    INTO v_retry_count, v_max_retries
    FROM strategies
    WHERE id = NEW.strategy_id;

    IF NEW.status = 'passed' THEN
        UPDATE strategies
        SET status = 'approved',
            validation_result = jsonb_build_object('level', NEW.level, 'status', NEW.status),
            updated_at = NOW()
        WHERE id = NEW.strategy_id;

        PERFORM publish_event(jsonb_build_object('event', 'validation.approved', 'strategy_id', NEW.strategy_id));

    ELSIF NEW.status = 'warning' THEN
        UPDATE strategies
        SET status = 'warning',
            validation_result = jsonb_build_object('level', NEW.level, 'status', NEW.status),
            updated_at = NOW()
        WHERE id = NEW.strategy_id;

        PERFORM publish_event(jsonb_build_object('event', 'validation.warning', 'strategy_id', NEW.strategy_id));

    ELSIF NEW.status = 'failed' THEN
        v_retry_count := COALESCE(v_retry_count, 0) + 1;

        IF v_retry_count >= COALESCE(v_max_retries, 3) THEN
            UPDATE strategies
            SET status = 'human_review',
                retry_count = v_retry_count,
                validation_result = jsonb_build_object('level', NEW.level, 'status', NEW.status),
                updated_at = NOW()
            WHERE id = NEW.strategy_id;

            PERFORM publish_event(jsonb_build_object('event', 'validation.max_retries', 'strategy_id', NEW.strategy_id));
        ELSE
            UPDATE strategies
            SET status = 'backtest_pending',
                retry_count = v_retry_count,
                validation_result = jsonb_build_object('level', NEW.level, 'status', NEW.status),
                updated_at = NOW()
            WHERE id = NEW.strategy_id;

            PERFORM publish_event(jsonb_build_object(
                'event', 'validation.rejected',
                'strategy_id', NEW.strategy_id,
                'retry_count', v_retry_count
            ));
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validation_result ON validations_v2;
CREATE TRIGGER trg_validation_result
AFTER INSERT ON validations_v2
FOR EACH ROW
EXECUTE FUNCTION handle_validation_result();
