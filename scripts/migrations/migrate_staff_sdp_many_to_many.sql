
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
