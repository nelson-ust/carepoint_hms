
-- Carepoint HMS Migration Script
-- Objective: Migrate Staff-to-SDP association from a 1:1 relationship to Many-to-Many.
-- Target: Tenant Database

BEGIN;

-- 1. Create the association table with standard Audit fields (BaseTable compliance)
CREATE TABLE IF NOT EXISTS staff_service_delivery_point_association (
    id SERIAL PRIMARY KEY,
    staff_profile_id INTEGER NOT NULL REFERENCES staff_profile(id) ON DELETE CASCADE,
    service_delivery_point_id INTEGER NOT NULL REFERENCES service_delivery_point(id) ON DELETE CASCADE,
    
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    
    date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    date_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    date_deleted TIMESTAMP WITH TIME ZONE,
    
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER,
    
    CONSTRAINT uq_staff_sdp_association UNIQUE (staff_profile_id, service_delivery_point_id)
);

-- 2. Create optimized indices for the join table
CREATE INDEX IF NOT EXISTS ix_staff_sdp_assoc_staff_id ON staff_service_delivery_point_association(staff_profile_id);
CREATE INDEX IF NOT EXISTS ix_staff_sdp_assoc_sdp_id ON staff_service_delivery_point_association(service_delivery_point_id);

-- 3. Data Migration: Populate the association table from existing staff profile records
INSERT INTO staff_service_delivery_point_association (
    staff_profile_id, 
    service_delivery_point_id,
    date_created,
    date_updated
)
SELECT 
    id, 
    service_delivery_point_id,
    date_created,
    now()
FROM staff_profile
WHERE service_delivery_point_id IS NOT NULL
ON CONFLICT (staff_profile_id, service_delivery_point_id) DO NOTHING;

-- 4. Finalize Schema Cleanup
-- Dropping the foreign key column from staff_profile to finalize the transition.
ALTER TABLE staff_profile DROP COLUMN IF EXISTS service_delivery_point_id;

COMMIT;




-- Migration Script: Enforce Service Point Validation
-- Purpose: Add visit_flow_step_id to core clinical and financial activity tables.

BEGIN;

-- 1. Vital Signs
ALTER TABLE vital_sign ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_vital_sign_visit_flow_step_id ON vital_sign(visit_flow_step_id);

-- 2. Clinical Consultations
ALTER TABLE consultation ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_consultation_visit_flow_step_id ON consultation(visit_flow_step_id);

-- 3. Laboratory Orders (Header)
ALTER TABLE lab_order ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_lab_order_visit_flow_step_id ON lab_order(visit_flow_step_id);

-- 4. Laboratory Order Items (Tracking Specimen Collection)
ALTER TABLE lab_order_item ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_lab_order_item_visit_flow_step_id ON lab_order_item(visit_flow_step_id);

-- 5. Laboratory Results
ALTER TABLE lab_result ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_lab_result_visit_flow_step_id ON lab_result(visit_flow_step_id);

-- 6. Prescriptions
ALTER TABLE prescription ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_prescription_visit_flow_step_id ON prescription(visit_flow_step_id);

-- 7. Payment Transactions
ALTER TABLE payment ADD COLUMN visit_flow_step_id INTEGER REFERENCES visit_flow_step(id);
CREATE INDEX idx_payment_visit_flow_step_id ON payment(visit_flow_step_id);

COMMIT;
