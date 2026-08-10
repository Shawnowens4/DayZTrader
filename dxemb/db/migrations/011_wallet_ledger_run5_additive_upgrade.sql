-- =============================================================
-- Slice 3 / Run 5 additive upgrade for wallet + ledger foundation
-- Purpose:
--   - Preserve historical 001 as-is
--   - Upgrade existing 001-applied schemas to Run 5 contract safely
--   - Keep column/table compatibility with local-safe wallet services
-- =============================================================

ALTER TABLE IF EXISTS wallet_account
    ADD COLUMN IF NOT EXISTS owner_kind TEXT;

UPDATE wallet_account
SET owner_kind = 'LOCAL_PLAYER'
WHERE owner_kind IS NULL OR BTRIM(owner_kind) = '';

ALTER TABLE IF EXISTS wallet_account
    ALTER COLUMN owner_kind SET DEFAULT 'LOCAL_PLAYER';

ALTER TABLE IF EXISTS wallet_account
    ALTER COLUMN owner_kind SET NOT NULL;

ALTER TABLE IF EXISTS wallet_account
    ADD COLUMN IF NOT EXISTS owner_label TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_account_owner_kind'
    ) THEN
        ALTER TABLE wallet_account
            ADD CONSTRAINT ck_wallet_account_owner_kind
            CHECK (owner_kind IN ('LOCAL_PLAYER', 'LOCAL_ADMIN', 'SYSTEM'));
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_account_owner_id_nonempty'
    ) THEN
        ALTER TABLE wallet_account
            ADD CONSTRAINT ck_wallet_account_owner_id_nonempty
            CHECK (BTRIM(discord_user_id) <> '');
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_wallet_account_owner_kind
    ON wallet_account (owner_kind, updated_at DESC);


DROP TRIGGER IF EXISTS trg_wallet_ledger_no_update ON wallet_ledger;
DROP TRIGGER IF EXISTS trg_wallet_ledger_no_delete ON wallet_ledger;


ALTER TABLE IF EXISTS wallet_ledger
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

UPDATE wallet_ledger
SET idempotency_key = CONCAT(reference_type, ':', reference_id)
WHERE idempotency_key IS NULL OR BTRIM(idempotency_key) = '';

WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY discord_user_id, idempotency_key
            ORDER BY id
        ) AS rn
    FROM wallet_ledger
)
UPDATE wallet_ledger wl
SET idempotency_key = CONCAT(wl.idempotency_key, ':', wl.id)
FROM ranked r
WHERE wl.id = r.id
  AND r.rn > 1;

ALTER TABLE IF EXISTS wallet_ledger
    ALTER COLUMN idempotency_key SET NOT NULL;


ALTER TABLE IF EXISTS wallet_ledger
    ADD COLUMN IF NOT EXISTS actor_source TEXT;

UPDATE wallet_ledger
SET actor_source = 'legacy_service'
WHERE actor_source IS NULL OR BTRIM(actor_source) = '';

ALTER TABLE IF EXISTS wallet_ledger
    ALTER COLUMN actor_source SET DEFAULT 'legacy_service';

ALTER TABLE IF EXISTS wallet_ledger
    ALTER COLUMN actor_source SET NOT NULL;


UPDATE wallet_ledger
SET reason_text = COALESCE(
    NULLIF(BTRIM(reason_code), ''),
    NULLIF(BTRIM(reference_type), ''),
    'wallet_entry'
)
WHERE reason_text IS NULL OR BTRIM(reason_text) = '';

UPDATE wallet_ledger
SET metadata = '{}'::jsonb
WHERE metadata IS NULL OR jsonb_typeof(metadata) IS DISTINCT FROM 'object';

DO $$
DECLARE
    c RECORD;
BEGIN
    FOR c IN
        SELECT conname
        FROM pg_constraint pc
        JOIN pg_class t ON t.oid = pc.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND t.relname = 'wallet_ledger'
          AND pc.contype = 'c'
          AND pg_get_constraintdef(pc.oid) ILIKE '%entry_type%'
    LOOP
        EXECUTE format('ALTER TABLE wallet_ledger DROP CONSTRAINT IF EXISTS %I', c.conname);
    END LOOP;
END;
$$;

UPDATE wallet_ledger
SET entry_type = 'ADMIN_ADJUSTMENT'
WHERE entry_type = 'ADJUSTMENT';

DO $$
DECLARE
    c RECORD;
BEGIN
    FOR c IN
        SELECT conname
        FROM pg_constraint pc
        JOIN pg_class t ON t.oid = pc.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND t.relname = 'wallet_ledger'
          AND pc.contype = 'c'
          AND pg_get_constraintdef(pc.oid) ILIKE '%entry_type%'
    LOOP
        EXECUTE format('ALTER TABLE wallet_ledger DROP CONSTRAINT IF EXISTS %I', c.conname);
    END LOOP;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_ledger_entry_type'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT ck_wallet_ledger_entry_type
            CHECK (entry_type IN (
                'CREDIT',
                'DEBIT',
                'ADMIN_ADJUSTMENT',
                'REVERSAL',
                'REFUND',
                'HOLD',
                'RELEASE'
            ));
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_wallet_ledger_idempotency'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT uq_wallet_ledger_idempotency
            UNIQUE (discord_user_id, idempotency_key);
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_ledger_owner_id_nonempty'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT ck_wallet_ledger_owner_id_nonempty
            CHECK (BTRIM(discord_user_id) <> '');
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_ledger_idempotency_nonempty'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT ck_wallet_ledger_idempotency_nonempty
            CHECK (BTRIM(idempotency_key) <> '');
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_ledger_actor_source_nonempty'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT ck_wallet_ledger_actor_source_nonempty
            CHECK (BTRIM(actor_source) <> '');
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_ledger_reason_present'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT ck_wallet_ledger_reason_present
            CHECK (
                COALESCE(
                    NULLIF(BTRIM(reason_text), ''),
                    NULLIF(BTRIM(reason_code), ''),
                    NULLIF(BTRIM(reference_type), '')
                ) IS NOT NULL
            );
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_ledger_metadata_object'
    ) THEN
        ALTER TABLE wallet_ledger
            ADD CONSTRAINT ck_wallet_ledger_metadata_object
            CHECK (jsonb_typeof(metadata) = 'object');
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user_idempotency
    ON wallet_ledger (discord_user_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_wallet_ledger_entry_type_created_at
    ON wallet_ledger (entry_type, created_at DESC);

CREATE OR REPLACE FUNCTION dxemb_wallet_ledger_before_insert()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.idempotency_key IS NULL OR BTRIM(NEW.idempotency_key) = '' THEN
        NEW.idempotency_key := CONCAT(NEW.reference_type, ':', NEW.reference_id);
    END IF;

    IF NEW.actor_source IS NULL OR BTRIM(NEW.actor_source) = '' THEN
        NEW.actor_source := 'legacy_service';
    END IF;

    IF NEW.reason_text IS NULL OR BTRIM(NEW.reason_text) = '' THEN
        NEW.reason_text := COALESCE(
            NULLIF(BTRIM(NEW.reason_code), ''),
            NULLIF(BTRIM(NEW.reference_type), ''),
            'wallet_entry'
        );
    END IF;

    IF NEW.metadata IS NULL OR jsonb_typeof(NEW.metadata) IS DISTINCT FROM 'object' THEN
        NEW.metadata := '{}'::jsonb;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wallet_ledger_before_insert ON wallet_ledger;
CREATE TRIGGER trg_wallet_ledger_before_insert
    BEFORE INSERT ON wallet_ledger
    FOR EACH ROW EXECUTE FUNCTION dxemb_wallet_ledger_before_insert();

DROP TRIGGER IF EXISTS trg_wallet_ledger_no_update ON wallet_ledger;
CREATE TRIGGER trg_wallet_ledger_no_update
    BEFORE UPDATE ON wallet_ledger
    FOR EACH ROW EXECUTE FUNCTION dxemb_wallet_ledger_immutable();

DROP TRIGGER IF EXISTS trg_wallet_ledger_no_delete ON wallet_ledger;
CREATE TRIGGER trg_wallet_ledger_no_delete
    BEFORE DELETE ON wallet_ledger
    FOR EACH ROW EXECUTE FUNCTION dxemb_wallet_ledger_immutable();