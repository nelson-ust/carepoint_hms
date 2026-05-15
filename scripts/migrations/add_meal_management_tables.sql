# scripts/migrations/add_meal_management_tables.sql
-- MIGRATION: DIETARY & MEAL MANAGEMENT
-- Purpose: Add tables for hospital meal catalog and order tracking with billing integration.

BEGIN;

-- 1. Meal Type Catalog
CREATE TABLE IF NOT EXISTS meal_type (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    billable_service_id INTEGER REFERENCES billable_service(id),
    name VARCHAR(150) NOT NULL,
    code VARCHAR(100) NOT NULL,
    description TEXT,
    base_price NUMERIC(14, 2) NOT NULL DEFAULT 0,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    date_created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_deleted TIMESTAMPTZ,
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER
);

CREATE INDEX IF NOT EXISTS ix_meal_type_code ON meal_type(code);
CREATE INDEX IF NOT EXISTS ix_meal_type_tenant_id ON meal_type(tenant_id);

-- 2. Meal Orders
CREATE TABLE IF NOT EXISTS meal_order (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    visit_id INTEGER NOT NULL REFERENCES visit(id),
    patient_id INTEGER NOT NULL REFERENCES patient(id),
    meal_type_id INTEGER NOT NULL REFERENCES meal_type(id),
    invoice_item_id INTEGER REFERENCES invoice_item(id), -- or billing_item.id depending on implementation
    
    recipient_type VARCHAR(50) NOT NULL DEFAULT 'PATIENT', -- PATIENT, CAREGIVER
    caregiver_name VARCHAR(200),
    status VARCHAR(50) NOT NULL DEFAULT 'ORDERED', -- ORDERED, PREPARING, SERVED, CANCELLED
    
    unit_price NUMERIC(14, 2) NOT NULL DEFAULT 0,
    quantity NUMERIC(14, 2) NOT NULL DEFAULT 1,
    total_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    
    ordered_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    served_at TIMESTAMPTZ,
    
    ordered_by_staff_id INTEGER,
    served_by_staff_id INTEGER,
    
    notes TEXT,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    date_created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_deleted TIMESTAMPTZ,
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER
);

CREATE INDEX IF NOT EXISTS ix_meal_order_visit_id ON meal_order(visit_id);
CREATE INDEX IF NOT EXISTS ix_meal_order_patient_id ON meal_order(patient_id);
CREATE INDEX IF NOT EXISTS ix_meal_order_status ON meal_order(status);
CREATE INDEX IF NOT EXISTS ix_meal_order_tenant_id ON meal_order(tenant_id);

COMMIT;
