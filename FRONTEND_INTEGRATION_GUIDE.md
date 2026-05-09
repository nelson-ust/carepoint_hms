# Carepoint HMS — Comprehensive Frontend Integration Guide

## 🚀 Overview
This document is the **Exhaustive API Reference** for the Carepoint HMS frontend team. It captures 100% of the endpoints defined in the backend, grouped by module.

### 🔑 Mandatory Headers
All requests (except public auth) must include:
- `Authorization: Bearer {{access_token}}`
- `X-Tenant-Code: {{tenant_slug}}`

---


## 📦 Module: ADMISSION
### GET /admissions/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /admissions/wards/{ward_id}/active
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /admissions/{admission_id}
**Response Body:**
```json
{
  "id": 0,
  "admission_no": "string",
  "patient_id": 0,
  "visit_id": 0,
  "ward_id": 0,
  "bed_id": 0,
  "admitted_by_staff_id": 0,
  "admission_status": "string",
  "admission_reason": "string",
  "admitted_at": "2026-05-09T00:00:00Z",
  "expected_discharge_at": "2026-05-09T00:00:00Z",
  "actual_discharge_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /admissions/
**Request Payload:**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "ward_id": 0,
  "bed_id": 0,
  "admitting_staff_id": 0,
  "admission_reason": "string",
  "admitted_at": "2026-05-09T00:00:00Z",
  "expected_discharge_at": "2026-05-09T00:00:00Z",
  "capture_first_bed_day_charge": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /admissions/from-visit
**Request Payload:**
```json
{
  "visit_id": 0,
  "ward_id": 0,
  "bed_id": 0,
  "admitting_staff_id": 0,
  "admission_reason": "string",
  "expected_discharge_at": "2026-05-09T00:00:00Z",
  "capture_first_bed_day_charge": false,
  "route_to_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /admissions/{admission_id}/transfer
**Request Payload:**
```json
{
  "new_bed_id": 0,
  "new_ward_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /admissions/{admission_id}/status
**Request Payload:**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /admissions/{admission_id}/bed-days
**Request Payload:**
```json
{
  "through_date": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission_id": 0,
  "charges_captured": 0,
  "total_amount_captured": 0.0,
  "captured_through": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: AMBULANCE
### GET /ambulances/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /ambulances/
**Request Payload:**
```json
{
  "code": "string",
  "plate_number": "string",
  "model": "string",
  "manufacturer": "string",
  "year_of_manufacture": 0,
  "color": "string",
  "current_mileage": 0.0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance": {
    "id": 0,
    "code": "string",
    "plate_number": "string",
    "model": "string",
    "manufacturer": "string",
    "year_of_manufacture": 0,
    "color": "string",
    "status": "string",
    "current_mileage": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /ambulances/{ambulance_id}
**Response Body:**
```json
{
  "id": 0,
  "code": "string",
  "plate_number": "string",
  "model": "string",
  "manufacturer": "string",
  "year_of_manufacture": 0,
  "color": "string",
  "status": "string",
  "current_mileage": 0.0,
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /ambulances/{ambulance_id}
**Request Payload:**
```json
{
  "model": "string",
  "manufacturer": "string",
  "year_of_manufacture": 0,
  "color": "string",
  "current_mileage": 0.0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance": {
    "id": 0,
    "code": "string",
    "plate_number": "string",
    "model": "string",
    "manufacturer": "string",
    "year_of_manufacture": 0,
    "color": "string",
    "status": "string",
    "current_mileage": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /ambulances/{ambulance_id}/status
**Request Payload:**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance": {
    "id": 0,
    "code": "string",
    "plate_number": "string",
    "model": "string",
    "manufacturer": "string",
    "year_of_manufacture": 0,
    "color": "string",
    "status": "string",
    "current_mileage": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /ambulances/{ambulance_id}
*No specific response schema found.*

### GET /ambulances/{ambulance_id}/readiness
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance_id": 0,
  "ready": false,
  "reasons": "string",
  "primary_driver_id": 0,
  "expired_equipment_ids": 0,
  "open_maintenance_ids": 0
}
```

### GET /ambulances/drivers/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /ambulances/drivers/
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "ambulance_id": 0,
  "driver_license_no": "string",
  "license_expiry_date": "2026-05-09T00:00:00Z",
  "is_primary_driver": false,
  "emergency_response_certified": false,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "driver": {
    "id": 0,
    "staff_profile_id": 0,
    "ambulance_id": 0,
    "driver_license_no": "string",
    "license_expiry_date": "2026-05-09T00:00:00Z",
    "is_primary_driver": false,
    "emergency_response_certified": false,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /ambulances/drivers/{driver_id}
**Request Payload:**
```json
{
  "license_expiry_date": "2026-05-09T00:00:00Z",
  "is_primary_driver": false,
  "emergency_response_certified": false,
  "ambulance_id": 0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "driver": {
    "id": 0,
    "staff_profile_id": 0,
    "ambulance_id": 0,
    "driver_license_no": "string",
    "license_expiry_date": "2026-05-09T00:00:00Z",
    "is_primary_driver": false,
    "emergency_response_certified": false,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /ambulances/drivers/{driver_id}
*No specific response schema found.*

### GET /ambulances/{ambulance_id}/equipment
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /ambulances/{ambulance_id}/equipment
**Request Payload:**
```json
{
  "ambulance_id": 0,
  "equipment_name": "string",
  "equipment_code": "string",
  "quantity": 0.0,
  "condition_status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "equipment": {
    "id": 0,
    "ambulance_id": 0,
    "equipment_name": "string",
    "equipment_code": "string",
    "quantity": 0.0,
    "condition_status": "string",
    "expiry_date": "2026-05-09T00:00:00Z",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /ambulances/equipment/{equipment_id}
**Request Payload:**
```json
{
  "equipment_name": "string",
  "quantity": 0.0,
  "condition_status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "equipment": {
    "id": 0,
    "ambulance_id": 0,
    "equipment_name": "string",
    "equipment_code": "string",
    "quantity": 0.0,
    "condition_status": "string",
    "expiry_date": "2026-05-09T00:00:00Z",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /ambulances/equipment/{equipment_id}
*No specific response schema found.*

### GET /ambulances/{ambulance_id}/maintenance
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /ambulances/{ambulance_id}/maintenance
**Request Payload:**
```json
{
  "ambulance_id": 0,
  "maintenance_type": "string",
  "issue_description": "string",
  "service_provider": "string",
  "maintenance_date": "2026-05-09T00:00:00Z",
  "cost": 0.0,
  "mileage_at_service": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "maintenance": {
    "id": 0,
    "ambulance_id": 0,
    "maintenance_status": "string",
    "maintenance_type": "string",
    "issue_description": "string",
    "service_provider": "string",
    "maintenance_date": "2026-05-09T00:00:00Z",
    "completed_date": "2026-05-09T00:00:00Z",
    "cost": 0.0,
    "mileage_at_service": 0.0
  }
}
```

### PUT /ambulances/maintenance/{maintenance_id}
**Request Payload:**
```json
{
  "maintenance_status": "string",
  "completed_date": "2026-05-09T00:00:00Z",
  "issue_description": "string",
  "service_provider": "string",
  "cost": 0.0,
  "mileage_at_service": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "maintenance": {
    "id": 0,
    "ambulance_id": 0,
    "maintenance_status": "string",
    "maintenance_type": "string",
    "issue_description": "string",
    "service_provider": "string",
    "maintenance_date": "2026-05-09T00:00:00Z",
    "completed_date": "2026-05-09T00:00:00Z",
    "cost": 0.0,
    "mileage_at_service": 0.0
  }
}
```


## 📦 Module: APPOINTMENT_EXTENSION
### POST /appointment-scheduling/reminders/schedule
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
[]
```

### POST /appointment-scheduling/reminders/dispatch-due
*No specific request payload schema found.*
*No specific response schema found.*

### POST /appointment-scheduling/history/{appointment_id}/log
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /appointment-scheduling/history/{appointment_id}
**Response Body:**
```json
[]
```

### POST /appointment-scheduling/recurrence
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### POST /appointment-scheduling/recurrence/{rule_id}/expand
*No specific request payload schema found.*
*No specific response schema found.*


## 📦 Module: APPOINTMENT
### GET /appointments/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /appointments/arrival-board
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /appointments/availability
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "available": false,
  "conflicts": 0
}
```

### GET /appointments/{appointment_id}
**Response Body:**
```json
{
  "id": 0,
  "appointment_code": "string",
  "patient_id": 0,
  "facility_id": 0,
  "service_delivery_point_id": 0,
  "staff_profile_id": 0,
  "scheduled_start_at": "2026-05-09T00:00:00Z",
  "scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string",
  "status": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /appointments/
**Request Payload:**
```json
{
  "patient_id": 0,
  "facility_id": 0,
  "service_delivery_point_id": 0,
  "staff_profile_id": 0,
  "scheduled_start_at": "2026-05-09T00:00:00Z",
  "scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /appointments/{appointment_id}/reschedule
**Request Payload:**
```json
{
  "new_scheduled_start_at": "2026-05-09T00:00:00Z",
  "new_scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /appointments/{appointment_id}/cancel
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /appointments/{appointment_id}/no-show
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /appointments/{appointment_id}/check-in
**Request Payload:**
```json
{
  "initiate_visit": false,
  "visit_flow_template_id": 0,
  "create_first_flow_step": false,
  "create_queue_ticket": false,
  "fast_track": false,
  "use_appointment_service_point": false,
  "visit_reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "visit_id": 0,
  "visit_code": "string",
  "queue_ticket_id": 0,
  "queue_number": "string",
  "queue_position": 0,
  "first_service_delivery_point_id": 0
}
```


## 📦 Module: APPROVAL
### GET /approvals/flows
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /approvals/flows
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "description": "string",
  "subject_type": "string",
  "is_default": false,
  "sla_hours": 0,
  "auto_cancel_after_hours": 0,
  "notify_on_submit": false,
  "notify_on_decision": false,
  "steps": []
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /approvals/flows/{flow_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PATCH /approvals/flows/{flow_id}
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "is_default": false,
  "is_active": false,
  "sla_hours": 0,
  "auto_cancel_after_hours": 0,
  "notify_on_submit": false,
  "notify_on_decision": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /approvals/flows/{flow_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /approvals/requests
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /approvals/requests/inbox
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /approvals/requests/mine
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /approvals/requests
**Request Payload:**
```json
{
  "flow_id": 0,
  "flow_code": "string",
  "subject_type": "string",
  "subject_id": 0,
  "title": "string",
  "description": "string",
  "payload": "string",
  "priority": "string",
  "department_id": 0,
  "facility_id": 0,
  "submit_now": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": [],
    "comments": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /approvals/requests/{request_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": [],
    "comments": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /approvals/requests/{request_id}/decisions
**Request Payload:**
```json
{
  "action": "string",
  "comment": "string",
  "delegated_to_user_id": 0,
  "step_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "decision": {
    "id": 0,
    "request_id": 0,
    "request_step_id": 0,
    "decided_by_user_id": 0,
    "action": "string",
    "comment": "string",
    "delegated_to_user_id": 0,
    "decided_at": "2026-05-09T00:00:00Z"
  },
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": [],
    "comments": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /approvals/requests/{request_id}/comments
**Request Payload:**
```json
{
  "body": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "comment": {
    "id": 0,
    "request_id": 0,
    "author_user_id": 0,
    "body": "string",
    "posted_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /approvals/requests/{request_id}/cancel
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": [],
    "comments": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /approvals/requests/{request_id}/force-close
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": [],
    "comments": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /approvals/requests/{request_id}/steps/{step_id}/reopen
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": [],
    "comments": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /approvals/maintenance/expire-stale
*No specific request payload schema found.*
*No specific response schema found.*


## 📦 Module: AUTH
### POST /auth/login
**Request Payload:**
```json
{
  "identifier": "string",
  "password": "string",
  "remember_me": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false
  },
  "tokens": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "string",
    "expires_in": 0,
    "refresh_expires_in": 0,
    "two_factor_required": false,
    "two_factor_verified": false
  }
}
```

### POST /auth/refresh
**Request Payload:**
```json
{
  "refresh_token": "string"
}
```
**Response Body:**
```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": 0
}
```

### POST /auth/impersonate
**Request Payload:**
```json
{
  "tenant_code": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "string",
  "tenant_code": "string",
  "tenant_name": "string"
}
```

### POST /auth/logout
**Request Payload:**
```json
{
  "refresh_token": "string",
  "all_sessions": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### GET /auth/me
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "tenant_id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false,
    "two_factor_method": "string",
    "two_factor_email_enabled": false,
    "two_factor_sms_enabled": false,
    "two_factor_whatsapp_enabled": false,
    "two_factor_authenticator_enabled": false,
    "roles": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "session": {
    "jti": "string",
    "issued_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "two_factor_verified": false,
    "ip_address": "string",
    "user_agent": "string"
  }
}
```

### POST /auth/change-password
**Request Payload:**
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_new_password": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /auth/forgot-password
**Request Payload:**
```json
{
  "identifier": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /auth/reset-password
**Request Payload:**
```json
{
  "reset_token": "string",
  "new_password": "string",
  "confirm_new_password": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /auth/otp/verify
**Request Payload:**
```json
{
  "user_id": 0,
  "identifier": "string",
  "otp_code": "string",
  "challenge_reference": "string",
  "purpose": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "verified": false,
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false
  },
  "tokens": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "string",
    "expires_in": 0,
    "refresh_expires_in": 0,
    "two_factor_required": false,
    "two_factor_verified": false
  }
}
```

### POST /auth/otp/resend
**Request Payload:**
```json
{
  "user_id": 0,
  "identifier": "string",
  "purpose": "string",
  "delivery_method": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```

### POST /auth/two-factor/setup
**Request Payload:**
```json
{
  "enable_two_factor": false,
  "method": "string",
  "enable_email": false,
  "enable_sms": false,
  "enable_whatsapp": false,
  "enable_authenticator": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "two_factor_enabled": false,
  "method": "string",
  "setup_secret": "string",
  "provisioning_uri": "string",
  "qr_code_data": "string"
}
```

### POST /auth/two-factor/verify
**Request Payload:**
```json
{
  "user_id": 0,
  "identifier": "string",
  "otp_code": "string",
  "method": "string",
  "challenge_reference": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "verified": false,
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false
  },
  "tokens": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "string",
    "expires_in": 0,
    "refresh_expires_in": 0,
    "two_factor_required": false,
    "two_factor_verified": false
  }
}
```

### POST /auth/email-verification/request
**Request Payload:**
```json
{
  "user_id": 0,
  "email": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```

### POST /auth/email-verification/confirm
**Request Payload:**
```json
{
  "token": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /auth/phone-verification/request
**Request Payload:**
```json
{
  "user_id": 0,
  "phone_number": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```

### POST /auth/phone-verification/confirm
**Request Payload:**
```json
{
  "token": "string",
  "otp_code": "string",
  "challenge_reference": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```


## 📦 Module: BED
### POST /beds/
**Request Payload:**
```json
{
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /beds/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /beds/{bed_id}
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /beds/{bed_id}/summary
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "ward": {
    "id": 0,
    "name": "string",
    "code": "string",
    "ward_type": "string",
    "description": "string"
  },
  "admission_count": 0,
  "has_active_admission": false
}
```

### PUT /beds/{bed_id}
**Request Payload:**
```json
{
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /beds/{bed_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```


## 📦 Module: BILLING
### GET /billing/services
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /billing/services
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "category": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service": {
    "id": 0,
    "code": "string",
    "name": "string",
    "category": "string",
    "default_price": 0.0,
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /billing/services/{sid}
**Request Payload:**
```json
{
  "name": "string",
  "category": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service": {
    "id": 0,
    "code": "string",
    "name": "string",
    "category": "string",
    "default_price": 0.0,
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /billing/services/{sid}
*No specific response schema found.*

### GET /billing/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /billing/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /billing/
**Request Payload:**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "patient_insurance_id": 0,
  "notes": "string",
  "items": []
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "billing": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "patient_insurance_id": 0,
    "billing_no": "string",
    "billing_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "gross_amount": 0.0,
    "discount_amount": 0.0,
    "net_amount": 0.0,
    "notes": "string",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /billing/{billing_id}
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "patient_insurance_id": 0,
  "billing_no": "string",
  "billing_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "gross_amount": 0.0,
  "discount_amount": 0.0,
  "net_amount": 0.0,
  "notes": "string",
  "items": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /billing/{billing_id}/items
**Request Payload:**
```json
{
  "service_name": "string",
  "service_code": "string",
  "quantity": 0.0,
  "unit_price": 0.0,
  "discount_amount": 0.0,
  "billable_service_id": 0,
  "source_reference": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "billing": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "patient_insurance_id": 0,
    "billing_no": "string",
    "billing_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "gross_amount": 0.0,
    "discount_amount": 0.0,
    "net_amount": 0.0,
    "notes": "string",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /billing/{billing_id}/cancel
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "billing": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "patient_insurance_id": 0,
    "billing_no": "string",
    "billing_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "gross_amount": 0.0,
    "discount_amount": 0.0,
    "net_amount": 0.0,
    "notes": "string",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: CLINICIAN
### GET /clinicians/
*No specific response schema found.*


## 📦 Module: COMPLIANCE
### GET /compliance/records
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /compliance/records
**Request Payload:**
```json
{
  "title": "string",
  "department_id": 0,
  "owner_staff_id": 0,
  "compliance_area": "string",
  "reference_code": "string",
  "due_date": "2026-05-09T00:00:00Z",
  "review_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "findings": "string",
  "action_plan": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "record": {
    "id": 0,
    "department_id": 0,
    "owner_staff_id": 0,
    "title": "string",
    "compliance_area": "string",
    "reference_code": "string",
    "due_date": "2026-05-09T00:00:00Z",
    "review_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "findings": "string",
    "action_plan": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /compliance/records/{record_id}
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "owner_staff_id": 0,
  "title": "string",
  "compliance_area": "string",
  "reference_code": "string",
  "due_date": "2026-05-09T00:00:00Z",
  "review_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "findings": "string",
  "action_plan": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /compliance/records/{record_id}
**Request Payload:**
```json
{
  "title": "string",
  "owner_staff_id": 0,
  "compliance_area": "string",
  "reference_code": "string",
  "due_date": "2026-05-09T00:00:00Z",
  "review_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "findings": "string",
  "action_plan": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "record": {
    "id": 0,
    "department_id": 0,
    "owner_staff_id": 0,
    "title": "string",
    "compliance_area": "string",
    "reference_code": "string",
    "due_date": "2026-05-09T00:00:00Z",
    "review_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "findings": "string",
    "action_plan": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /compliance/records/{record_id}
*No specific response schema found.*

### GET /compliance/accreditations
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /compliance/accreditations
**Request Payload:**
```json
{
  "accreditation_body": "string",
  "accreditation_name": "string",
  "department_id": 0,
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "accreditation": {
    "id": 0,
    "department_id": 0,
    "accreditation_body": "string",
    "accreditation_name": "string",
    "certificate_no": "string",
    "issue_date": "2026-05-09T00:00:00Z",
    "expiry_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /compliance/accreditations/{accreditation_id}
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "accreditation_body": "string",
  "accreditation_name": "string",
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```

### PUT /compliance/accreditations/{accreditation_id}
**Request Payload:**
```json
{
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "accreditation": {
    "id": 0,
    "department_id": 0,
    "accreditation_body": "string",
    "accreditation_name": "string",
    "certificate_no": "string",
    "issue_date": "2026-05-09T00:00:00Z",
    "expiry_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /compliance/accreditations/{accreditation_id}
*No specific response schema found.*

### GET /compliance/incidents
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /compliance/incidents
**Request Payload:**
```json
{
  "summary": "string",
  "incident_date": "2026-05-09T00:00:00Z",
  "severity": "string",
  "category": "string",
  "department_id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "reported_by_staff_id": 0,
  "immediate_action_taken": "string",
  "follow_up_required": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "incident": {
    "id": 0,
    "incident_no": "string",
    "incident_date": "2026-05-09T00:00:00Z",
    "severity": "string",
    "category": "string",
    "summary": "string",
    "immediate_action_taken": "string",
    "follow_up_required": false,
    "department_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "reported_by_staff_id": 0,
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /compliance/incidents/{incident_id}
**Response Body:**
```json
{
  "id": 0,
  "incident_no": "string",
  "incident_date": "2026-05-09T00:00:00Z",
  "severity": "string",
  "category": "string",
  "summary": "string",
  "immediate_action_taken": "string",
  "follow_up_required": false,
  "department_id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "reported_by_staff_id": 0,
  "created_at": "2026-05-09T00:00:00Z"
}
```

### PUT /compliance/incidents/{incident_id}
**Request Payload:**
```json
{
  "severity": "string",
  "category": "string",
  "immediate_action_taken": "string",
  "follow_up_required": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "incident": {
    "id": 0,
    "incident_no": "string",
    "incident_date": "2026-05-09T00:00:00Z",
    "severity": "string",
    "category": "string",
    "summary": "string",
    "immediate_action_taken": "string",
    "follow_up_required": false,
    "department_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "reported_by_staff_id": 0,
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /compliance/infection-logs
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /compliance/infection-logs
**Request Payload:**
```json
{
  "log_date": "2026-05-09T00:00:00Z",
  "details": "string",
  "department_id": 0,
  "recorded_by_staff_id": 0,
  "infection_type": "string",
  "affected_area": "string",
  "action_taken": "string",
  "outcome": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "log": {
    "id": 0,
    "department_id": 0,
    "recorded_by_staff_id": 0,
    "log_date": "2026-05-09T00:00:00Z",
    "infection_type": "string",
    "affected_area": "string",
    "details": "string",
    "action_taken": "string",
    "outcome": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /compliance/infection-logs/{log_id}
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "recorded_by_staff_id": 0,
  "log_date": "2026-05-09T00:00:00Z",
  "infection_type": "string",
  "affected_area": "string",
  "details": "string",
  "action_taken": "string",
  "outcome": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```

### GET /compliance/quality-projects
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /compliance/quality-projects
**Request Payload:**
```json
{
  "title": "string",
  "department_id": 0,
  "project_lead_staff_id": 0,
  "objective": "string",
  "problem_statement": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "outcome_summary": "string",
  "recommendations": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "project": {
    "id": 0,
    "department_id": 0,
    "project_lead_staff_id": 0,
    "title": "string",
    "objective": "string",
    "problem_statement": "string",
    "start_date": "2026-05-09T00:00:00Z",
    "end_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "outcome_summary": "string",
    "recommendations": "string"
  }
}
```

### GET /compliance/quality-projects/{project_id}
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "project_lead_staff_id": 0,
  "title": "string",
  "objective": "string",
  "problem_statement": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "outcome_summary": "string",
  "recommendations": "string"
}
```

### PUT /compliance/quality-projects/{project_id}
**Request Payload:**
```json
{
  "objective": "string",
  "problem_statement": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "outcome_summary": "string",
  "recommendations": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "project": {
    "id": 0,
    "department_id": 0,
    "project_lead_staff_id": 0,
    "title": "string",
    "objective": "string",
    "problem_statement": "string",
    "start_date": "2026-05-09T00:00:00Z",
    "end_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "outcome_summary": "string",
    "recommendations": "string"
  }
}
```

### GET /compliance/dashboard
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "compliance_due_soon": 0,
  "compliance_overdue": 0,
  "accreditations_expiring_soon": 0,
  "accreditations_expired": 0,
  "incidents_open_critical": 0,
  "incidents_open_high": 0,
  "quality_projects_active": 0
}
```


## 📦 Module: CONSULTATION
### GET /consultations/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /consultations/
**Request Payload:**
```json
{
  "visit_id": 0,
  "clinician_staff_id": 0,
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /consultations/{consultation_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "clinician_staff_id": 0,
  "status": "string",
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string",
  "consultation_started_at": "2026-05-09T00:00:00Z",
  "consultation_ended_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /consultations/{consultation_id}
**Request Payload:**
```json
{
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /consultations/{consultation_id}/finalize
**Request Payload:**
```json
{
  "next_service_delivery_point_id": 0,
  "end_visit": false,
  "closing_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /consultations/{consultation_id}/cancel
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: DATABASE_BACKUP
### GET /backups
**Response Body:**
```json
[]
```

### POST /backups
*No specific request payload schema found.*
**Response Body:**
```json
{
  "id": 0,
  "filename": "string",
  "s3_url": "string",
  "s3_key": "string",
  "size_bytes": 0,
  "status": "string",
  "error_message": "string",
  "is_encrypted": false,
  "encryption_algo": "string",
  "checksum_sha256": "string",
  "backup_type": "string",
  "pg_dump_format": "string",
  "backup_started_at": "2026-05-09T00:00:00Z",
  "backup_finished_at": "2026-05-09T00:00:00Z",
  "pitr_lsn": "string",
  "pitr_timestamp": "2026-05-09T00:00:00Z",
  "retention_until": "2026-05-09T00:00:00Z",
  "triggered_by": "string",
  "date_created": "2026-05-09T00:00:00Z"
}
```

### GET /backups/{backup_id}/download
*No specific response schema found.*

### POST /backups/{backup_id}/restore
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /backups/retention/sweep
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: DEPARTMENT
### POST /departments/
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false,
  "id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /departments/
**Response Body:**
```json
{
  "success": false,
  "items": [],
  "count": 0
}
```

### GET /departments/{department_id}
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false,
  "id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PATCH /departments/{department_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false,
  "id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /departments/{department_id}
*No specific response schema found.*


## 📦 Module: DIAGNOSIS
### GET /diagnoses/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /diagnoses/
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "diagnosis_name": "string",
  "diagnosis_code": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "diagnosis": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "diagnosis_code": "string",
    "diagnosis_name": "string",
    "diagnosis_type": "string",
    "diagnosis_note": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /diagnoses/{diagnosis_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "diagnosis_code": "string",
  "diagnosis_name": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /diagnoses/{diagnosis_id}
**Request Payload:**
```json
{
  "diagnosis_name": "string",
  "diagnosis_code": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "diagnosis": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "diagnosis_code": "string",
    "diagnosis_name": "string",
    "diagnosis_type": "string",
    "diagnosis_note": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: DISCHARGE
### POST /discharges/
**Request Payload:**
```json
{
  "admission_id": 0,
  "discharged_by_staff_id": 0,
  "discharge_date": "2026-05-09T00:00:00Z",
  "discharge_condition": "string",
  "discharge_summary": "string",
  "follow_up_instruction": "string",
  "capture_final_bed_day_charges": false,
  "end_visit_if_only_open_event": false,
  "force": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "discharge": {
    "id": 0,
    "admission_id": 0,
    "discharged_by_staff_id": 0,
    "discharge_date": "2026-05-09T00:00:00Z",
    "discharge_condition": "string",
    "discharge_summary": "string",
    "follow_up_instruction": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "admission_id": 0,
  "bed_day_charges_captured": 0,
  "visit_completed": false
}
```

### GET /discharges/admissions/{admission_id}/readiness
*No specific response schema found.*

### GET /discharges/{discharge_id}
**Response Body:**
```json
{
  "id": 0,
  "admission_id": 0,
  "discharged_by_staff_id": 0,
  "discharge_date": "2026-05-09T00:00:00Z",
  "discharge_condition": "string",
  "discharge_summary": "string",
  "follow_up_instruction": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /discharges/admissions/{admission_id}
**Response Body:**
```json
{
  "id": 0,
  "admission_id": 0,
  "discharged_by_staff_id": 0,
  "discharge_date": "2026-05-09T00:00:00Z",
  "discharge_condition": "string",
  "discharge_summary": "string",
  "follow_up_instruction": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: DISPENSE
### POST /dispenses/
**Request Payload:**
```json
{
  "prescription_id": 0,
  "dispensed_by_staff_id": 0,
  "note": "string",
  "items": [],
  "store_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispense": {
    "id": 0,
    "prescription_id": 0,
    "dispensed_by_staff_id": 0,
    "dispense_no": "string",
    "status": "string",
    "dispensed_at": "2026-05-09T00:00:00Z",
    "note": "string",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /dispenses/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /dispenses/prescriptions/{prescription_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /dispenses/{dispense_id}
**Response Body:**
```json
{
  "id": 0,
  "prescription_id": 0,
  "dispensed_by_staff_id": 0,
  "dispense_no": "string",
  "status": "string",
  "dispensed_at": "2026-05-09T00:00:00Z",
  "note": "string",
  "items": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: DOCTOR_CALENDAR
### GET /doctor-calendar/templates
**Response Body:**
```json
[]
```

### POST /doctor-calendar/templates
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### POST /doctor-calendar/templates/{template_id}/deactivate
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### POST /doctor-calendar/time-off
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### POST /doctor-calendar/slots/materialise
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /doctor-calendar/slots
**Response Body:**
```json
[]
```

### GET /doctor-calendar/workload/{staff_profile_id}
*No specific response schema found.*

### POST /doctor-calendar/slots/{slot_id}/reserve
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### POST /doctor-calendar/slots/{slot_id}/release
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```


## 📦 Module: DRUG
### GET /drugs/categories
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /drugs/categories
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "category": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /drugs/categories/{cat_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "category": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /drugs/categories/{cat_id}
*No specific response schema found.*

### GET /drugs/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /drugs/
**Request Payload:**
```json
{
  "name": "string",
  "generic_name": "string",
  "brand_name": "string",
  "strength": "string",
  "dosage_form": "string",
  "pack_size": "string",
  "sku": "string",
  "drug_category_id": 0,
  "unit_price": 0.0,
  "reorder_level": 0.0,
  "is_controlled": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "drug": {
    "id": 0,
    "name": "string",
    "generic_name": "string",
    "brand_name": "string",
    "strength": "string",
    "dosage_form": "string",
    "pack_size": "string",
    "sku": "string",
    "drug_category_id": 0,
    "unit_price": 0.0,
    "reorder_level": 0.0,
    "is_controlled": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /drugs/{drug_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "generic_name": "string",
  "brand_name": "string",
  "strength": "string",
  "dosage_form": "string",
  "pack_size": "string",
  "sku": "string",
  "drug_category_id": 0,
  "unit_price": 0.0,
  "reorder_level": 0.0,
  "is_controlled": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /drugs/{drug_id}
**Request Payload:**
```json
{
  "name": "string",
  "generic_name": "string",
  "brand_name": "string",
  "strength": "string",
  "dosage_form": "string",
  "pack_size": "string",
  "sku": "string",
  "drug_category_id": 0,
  "unit_price": 0.0,
  "reorder_level": 0.0,
  "is_controlled": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "drug": {
    "id": 0,
    "name": "string",
    "generic_name": "string",
    "brand_name": "string",
    "strength": "string",
    "dosage_form": "string",
    "pack_size": "string",
    "sku": "string",
    "drug_category_id": 0,
    "unit_price": 0.0,
    "reorder_level": 0.0,
    "is_controlled": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /drugs/{drug_id}
*No specific response schema found.*


## 📦 Module: FACILITY
### GET /facilities
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "facility_type": "string",
    "status": "string",
    "phone_number": "string",
    "email": "string",
    "website": "string",
    "address_line_1": "string",
    "address_line_2": "string",
    "city": "string",
    "state": "string",
    "country": "string",
    "postal_code": "string",
    "timezone": "string",
    "id": 0,
    "network_id": 0,
    "parent_facility_id": 0,
    "network": {
      "name": "string",
      "code": "string",
      "description": "string",
      "id": 0,
      "head_office_facility_id": 0
    },
    "service_areas": [
      {
        "area_name": "string",
        "region_code": "string",
        "notes": "string",
        "id": 0,
        "facility_id": 0
      }
    ]
  }
]
```

### GET /facilities/{facility_id}
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "id": 0,
  "network_id": 0,
  "parent_facility_id": 0,
  "network": {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  },
  "service_areas": [
    {
      "area_name": "string",
      "region_code": "string",
      "notes": "string",
      "id": 0,
      "facility_id": 0
    }
  ]
}
```

### POST /facilities
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "network_id": 0,
  "parent_facility_id": 0
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "id": 0,
  "network_id": 0,
  "parent_facility_id": 0,
  "network": {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  },
  "service_areas": [
    {
      "area_name": "string",
      "region_code": "string",
      "notes": "string",
      "id": 0,
      "facility_id": 0
    }
  ]
}
```

### PUT /facilities/{facility_id}
**Request Payload:**
```json
{
  "name": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "address_line_1": "string",
  "city": "string",
  "state": "string",
  "network_id": 0,
  "parent_facility_id": 0
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "id": 0,
  "network_id": 0,
  "parent_facility_id": 0,
  "network": {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  },
  "service_areas": [
    {
      "area_name": "string",
      "region_code": "string",
      "notes": "string",
      "id": 0,
      "facility_id": 0
    }
  ]
}
```

### DELETE /facilities/{facility_id}
*No specific response schema found.*

### GET /facilities/networks/all
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  }
]
```

### POST /facilities/networks/create
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "head_office_facility_id": 0
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0,
  "head_office_facility_id": 0
}
```

### PUT /facilities/networks/{network_id}
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "head_office_facility_id": 0
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0,
  "head_office_facility_id": 0
}
```

### DELETE /facilities/networks/{network_id}
*No specific response schema found.*

### GET /facilities/service-areas/all
**Response Body:**
```json
[
  {
    "area_name": "string",
    "region_code": "string",
    "notes": "string",
    "id": 0,
    "facility_id": 0
  }
]
```

### POST /facilities/service-areas/create
**Request Payload:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "facility_id": 0
}
```
**Response Body:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "id": 0,
  "facility_id": 0
}
```

### PUT /facilities/service-areas/{area_id}
**Request Payload:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "id": 0,
  "facility_id": 0
}
```

### DELETE /facilities/service-areas/{area_id}
*No specific response schema found.*


## 📦 Module: HR_PAYROLL
### POST /hr/payroll-config/allowance-types
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "is_taxable": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "is_taxable": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false,
  "id": 0
}
```

### GET /hr/payroll-config/allowance-types
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "is_taxable": false,
    "default_amount": 0.0,
    "default_percent_of_base": 0.0,
    "description": "string",
    "is_active": false,
    "id": 0
  }
]
```

### POST /hr/payroll-config/deduction-types
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "is_statutory": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "is_statutory": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false,
  "id": 0
}
```

### GET /hr/payroll-config/deduction-types
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "is_statutory": false,
    "default_amount": 0.0,
    "default_percent_of_base": 0.0,
    "description": "string",
    "is_active": false,
    "id": 0
  }
]
```

### POST /hr/payroll-config/statutory-configs
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "rate_percent": 0.0,
  "bands_json": [
    "string"
  ],
  "employer_rate_percent": 0.0,
  "effective_from": "2026-05-09T00:00:00Z",
  "effective_to": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "rate_percent": 0.0,
  "bands_json": [
    "string"
  ],
  "employer_rate_percent": 0.0,
  "effective_from": "2026-05-09T00:00:00Z",
  "effective_to": "2026-05-09T00:00:00Z",
  "note": "string",
  "id": 0
}
```

### GET /hr/payroll-config/statutory-configs
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "rate_percent": 0.0,
    "bands_json": [
      "string"
    ],
    "employer_rate_percent": 0.0,
    "effective_from": "2026-05-09T00:00:00Z",
    "effective_to": "2026-05-09T00:00:00Z",
    "note": "string",
    "id": 0
  }
]
```


## 📦 Module: HR
### POST /hr/onboarding/{staff_profile_id}/seed
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/onboarding/items/{item_id}/complete
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/offboarding/{staff_profile_id}/seed
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/offboarding/items/{item_id}/complete
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/profiles/{staff_profile_id}/status
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/profiles/{staff_profile_id}/status-history
*No specific response schema found.*

### POST /hr/contracts
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/contracts
*No specific response schema found.*

### POST /hr/documents
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/documents
*No specific response schema found.*

### POST /hr/licenses
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/licenses
*No specific response schema found.*

### POST /hr/licenses/sweep-expiries
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/roster/shift-templates
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/roster/shift-templates
*No specific response schema found.*

### POST /hr/roster/rosters
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/roster/assignments
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/roster/assignments/{assignment_id}/swap
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/roster/assignments
*No specific response schema found.*

### POST /hr/attendance/clock-in
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/attendance/clock-out
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/attendance
*No specific response schema found.*

### POST /hr/timesheets/generate
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/timesheets/{timesheet_id}/submit
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/timesheets/{timesheet_id}/approve
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/timesheets/{timesheet_id}/lock
*No specific request payload schema found.*
*No specific response schema found.*

### GET /hr/timesheets
*No specific response schema found.*

### POST /hr/leave/types
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/leave/types
*No specific response schema found.*

### POST /hr/leave/requests
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "leave_type_id": 0,
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "days_requested": 0.0,
  "reason": "string",
  "handover_notes": "string",
  "cover_staff_id": 0
}
```
*No specific response schema found.*

### POST /hr/leave/requests/{request_id}/decide
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/leave/requests
*No specific response schema found.*

### GET /hr/leave/balances
*No specific response schema found.*

### POST /hr/leave/holidays
**Request Payload:**
```json
{
  "key": "value"
}
```
*No specific response schema found.*

### GET /hr/leave/holidays
*No specific response schema found.*

### POST /hr/payroll/runs
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/payroll/runs/{run_id}/calculate
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/payroll/runs/{run_id}/approve
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/payroll/runs/{run_id}/lock
*No specific request payload schema found.*
*No specific response schema found.*

### GET /hr/payroll/runs
*No specific response schema found.*

### GET /hr/payroll/runs/{run_id}/lines
*No specific response schema found.*

### POST /hr/overtime
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/overtime/{record_id}/decide
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/loans
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/loans/{loan_id}/approve
*No specific request payload schema found.*
*No specific response schema found.*

### POST /hr/loans/{loan_id}/repay
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/payroll/salary
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/tasks
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/tasks
*No specific response schema found.*

### POST /hr/announcements
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/announcements
*No specific response schema found.*

### POST /hr/incidents
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/incidents/actions
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/requests
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/requests/{request_id}/decide
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/appraisals/cycles
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /hr/training/records
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### GET /hr/reports/headcount
*No specific response schema found.*

### GET /hr/audit-log
*No specific response schema found.*


## 📦 Module: INTEGRATION
### GET /integrations/
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "base_url": "string",
    "protocol": 0,
    "provider_type": 0,
    "direction": 0,
    "is_active": false,
    "id": 0,
    "credentials": [
      {
        "credential_type": "string",
        "secret_reference": "string",
        "id": 0
      }
    ]
  }
]
```

### POST /integrations/
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "credentials": [
    {
      "credential_type": "string",
      "secret_reference": "string"
    }
  ]
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "id": 0,
  "credentials": [
    {
      "credential_type": "string",
      "secret_reference": "string",
      "id": 0
    }
  ]
}
```

### GET /integrations/{endpoint_id}
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "id": 0,
  "credentials": [
    {
      "credential_type": "string",
      "secret_reference": "string",
      "id": 0
    }
  ]
}
```

### PUT /integrations/{endpoint_id}
**Request Payload:**
```json
{
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "id": 0,
  "credentials": [
    {
      "credential_type": "string",
      "secret_reference": "string",
      "id": 0
    }
  ]
}
```

### DELETE /integrations/{endpoint_id}
*No specific response schema found.*


## 📦 Module: INVENTORY
### GET /inventory/stores
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /inventory/stores
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "location_description": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "store": {
    "id": 0,
    "name": "string",
    "code": "string",
    "location_description": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /inventory/stores/{store_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "location_description": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /inventory/stores/{store_id}
**Request Payload:**
```json
{
  "name": "string",
  "location_description": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "store": {
    "id": 0,
    "name": "string",
    "code": "string",
    "location_description": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /inventory/stores/{store_id}
*No specific response schema found.*

### GET /inventory/items
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /inventory/items
**Request Payload:**
```json
{
  "store_id": 0,
  "drug_id": 0,
  "item_type": "string",
  "item_name": "string",
  "sku": "string",
  "unit_of_measure": "string",
  "quantity_on_hand": 0.0,
  "reorder_level": 0.0,
  "unit_cost": 0.0,
  "expiry_date": "2026-05-09T00:00:00Z",
  "batch_no": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "stock_item": {
    "id": 0,
    "store_id": 0,
    "drug_id": 0,
    "item_type": "string",
    "item_name": "string",
    "sku": "string",
    "unit_of_measure": "string",
    "quantity_on_hand": 0.0,
    "reorder_level": 0.0,
    "unit_cost": 0.0,
    "expiry_date": "2026-05-09T00:00:00Z",
    "batch_no": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /inventory/items/{item_id}
**Response Body:**
```json
{
  "id": 0,
  "store_id": 0,
  "drug_id": 0,
  "item_type": "string",
  "item_name": "string",
  "sku": "string",
  "unit_of_measure": "string",
  "quantity_on_hand": 0.0,
  "reorder_level": 0.0,
  "unit_cost": 0.0,
  "expiry_date": "2026-05-09T00:00:00Z",
  "batch_no": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /inventory/items/{item_id}
**Request Payload:**
```json
{
  "item_name": "string",
  "sku": "string",
  "unit_of_measure": "string",
  "reorder_level": 0.0,
  "unit_cost": 0.0,
  "expiry_date": "2026-05-09T00:00:00Z",
  "batch_no": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "stock_item": {
    "id": 0,
    "store_id": 0,
    "drug_id": 0,
    "item_type": "string",
    "item_name": "string",
    "sku": "string",
    "unit_of_measure": "string",
    "quantity_on_hand": 0.0,
    "reorder_level": 0.0,
    "unit_cost": 0.0,
    "expiry_date": "2026-05-09T00:00:00Z",
    "batch_no": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /inventory/items/{item_id}
*No specific response schema found.*

### GET /inventory/movements
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /inventory/movements
**Request Payload:**
```json
{
  "store_id": 0,
  "stock_item_id": 0,
  "movement_type": "string",
  "quantity": 0.0,
  "reference_no": "string",
  "note": "string",
  "performed_by_staff_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "movement": {
    "id": 0,
    "store_id": 0,
    "stock_item_id": 0,
    "performed_by_staff_id": 0,
    "movement_type": "string",
    "reference_no": "string",
    "quantity": 0.0,
    "balance_after": 0.0,
    "movement_date": "2026-05-09T00:00:00Z",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /inventory/movements/{movement_id}
**Response Body:**
```json
{
  "id": 0,
  "store_id": 0,
  "stock_item_id": 0,
  "performed_by_staff_id": 0,
  "movement_type": "string",
  "reference_no": "string",
  "quantity": 0.0,
  "balance_after": 0.0,
  "movement_date": "2026-05-09T00:00:00Z",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: INVITATION
### POST /invitations
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /invitations
**Response Body:**
```json
[]
```

### POST /invitations/{invitation_id}/cancel
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### POST /invitations/{invitation_id}/resend
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### POST /invitations/sweep
*No specific request payload schema found.*
*No specific response schema found.*

### POST /invitations/accept
**Request Payload:**
```json
"string"
```
*No specific response schema found.*


## 📦 Module: INVOICE
### GET /invoices/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /invoices/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /invoices/issue-from-billing
**Request Payload:**
```json
{
  "billing_id": 0,
  "payer_id": 0,
  "due_date": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "invoice": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "billing_id": 0,
    "payer_id": 0,
    "invoice_no": "string",
    "status": "string",
    "invoice_date": "2026-05-09T00:00:00Z",
    "due_date": "2026-05-09T00:00:00Z",
    "subtotal_amount": 0.0,
    "discount_amount": 0.0,
    "tax_amount": 0.0,
    "total_amount": 0.0,
    "amount_paid": 0.0,
    "balance_due": 0.0,
    "note": "string",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /invoices/{invoice_id}
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "billing_id": 0,
  "payer_id": 0,
  "invoice_no": "string",
  "status": "string",
  "invoice_date": "2026-05-09T00:00:00Z",
  "due_date": "2026-05-09T00:00:00Z",
  "subtotal_amount": 0.0,
  "discount_amount": 0.0,
  "tax_amount": 0.0,
  "total_amount": 0.0,
  "amount_paid": 0.0,
  "balance_due": 0.0,
  "note": "string",
  "items": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /invoices/{invoice_id}/void
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "invoice": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "billing_id": 0,
    "payer_id": 0,
    "invoice_no": "string",
    "status": "string",
    "invoice_date": "2026-05-09T00:00:00Z",
    "due_date": "2026-05-09T00:00:00Z",
    "subtotal_amount": 0.0,
    "discount_amount": 0.0,
    "tax_amount": 0.0,
    "total_amount": 0.0,
    "amount_paid": 0.0,
    "balance_due": 0.0,
    "note": "string",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: LAB_ORDER
### GET /lab/orders/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /lab/orders/worklist
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /lab/orders/
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "clinical_note": "string",
  "items": [],
  "auto_capture_charge": false,
  "route_to_lab_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /lab/orders/{order_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "order_no": "string",
  "status": "string",
  "clinical_note": "string",
  "ordered_at": "2026-05-09T00:00:00Z",
  "items": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /lab/orders/items/{item_id}/collect-specimen
**Request Payload:**
```json
{
  "specimen_id": "string",
  "collected_by_staff_id": 0,
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /lab/orders/items/{item_id}/start-processing
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /lab/orders/items/{item_id}/cancel
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /lab/orders/{order_id}/cancel
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: LAB_RESULT
### POST /lab/results/
**Request Payload:**
```json
{
  "lab_order_item_id": 0,
  "entered_by_staff_id": 0,
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /lab/results/{result_id}
**Request Payload:**
```json
{
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /lab/results/{result_id}/verify
**Request Payload:**
```json
{
  "verified_by_staff_id": 0,
  "verification_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /lab/results/{result_id}/release
**Request Payload:**
```json
{
  "release_note": "string",
  "notify_clinician": false,
  "route_to_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /lab/results/{result_id}/cancel
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /lab/results/{result_id}
**Response Body:**
```json
{
  "id": 0,
  "lab_order_item_id": 0,
  "entered_by_staff_id": 0,
  "verified_by_staff_id": 0,
  "result_status": "string",
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string",
  "entered_at": "2026-05-09T00:00:00Z",
  "verified_at": "2026-05-09T00:00:00Z",
  "released_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /lab/results/by-item/{item_id}
**Response Body:**
```json
{
  "id": 0,
  "lab_order_item_id": 0,
  "entered_by_staff_id": 0,
  "verified_by_staff_id": 0,
  "result_status": "string",
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string",
  "entered_at": "2026-05-09T00:00:00Z",
  "verified_at": "2026-05-09T00:00:00Z",
  "released_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: LAB
### GET /lab/tests/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /lab/tests/
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "sample_type": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_test": {
    "id": 0,
    "code": "string",
    "name": "string",
    "sample_type": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "default_price": 0.0,
    "description": "string",
    "is_active": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /lab/tests/{test_id}
**Response Body:**
```json
{
  "id": 0,
  "code": "string",
  "name": "string",
  "sample_type": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "default_price": 0.0,
  "description": "string",
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /lab/tests/{test_id}
**Request Payload:**
```json
{
  "name": "string",
  "sample_type": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_test": {
    "id": 0,
    "code": "string",
    "name": "string",
    "sample_type": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "default_price": 0.0,
    "description": "string",
    "is_active": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /lab/tests/{test_id}
*No specific response schema found.*


## 📦 Module: LEAVE_REQUEST
### POST /leave-requests
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "leave_type_id": 0,
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "days_requested": 0.0,
  "reason": "string",
  "handover_notes": "string",
  "cover_staff_id": 0
}
```
**Response Body:**
```json
"string"
```

### GET /leave-requests
**Response Body:**
```json
"string"
```

### GET /leave-requests/{request_id}
**Response Body:**
```json
"string"
```

### PUT /leave-requests/{request_id}
**Request Payload:**
```json
{
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "days_requested": 0.0,
  "reason": "string",
  "handover_notes": "string",
  "cover_staff_id": 0
}
```
**Response Body:**
```json
"string"
```

### DELETE /leave-requests/{request_id}
*No specific response schema found.*

### POST /leave-requests/{request_id}/submit
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```


## 📦 Module: LOYALTY
### POST /loyalty-network/programs
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "points_per_currency_unit": 0.0,
  "minimum_redemption_points": 0.0,
  "is_auto_enroll": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "points_per_currency_unit": 0.0,
  "minimum_redemption_points": 0.0,
  "is_auto_enroll": false,
  "id": 0
}
```

### GET /loyalty-network/programs
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "description": "string",
    "points_per_currency_unit": 0.0,
    "minimum_redemption_points": 0.0,
    "is_auto_enroll": false,
    "id": 0
  }
]
```

### POST /loyalty-network/networks
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0
}
```

### GET /loyalty-network/networks
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0
  }
]
```


## 📦 Module: MEDICAL_HISTORY
### GET /patients/{patient_id}/medical-history
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "history": {
    "patient": {
      "id": 0,
      "hospital_number": "string",
      "first_name": "string",
      "last_name": "string",
      "middle_name": "string",
      "date_of_birth": "2026-05-09T00:00:00Z",
      "age_years": 0,
      "gender": "string",
      "blood_group": "string",
      "genotype": "string",
      "allergies": "string",
      "patient_type": "string",
      "phone_number": "string",
      "email": "string",
      "chronic_conditions": "string"
    },
    "summary": "string",
    "allergies": "string",
    "visits": [],
    "consultations": [],
    "diagnoses": [],
    "lab_orders": [],
    "radiology_orders": [],
    "prescriptions": [],
    "procedure_orders": [],
    "surgical_cases": [],
    "admissions": [],
    "triage_assessments": [],
    "vital_signs": []
  }
}
```

### GET /visits/{visit_id}/medical-history
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "history": {
    "patient": {
      "id": 0,
      "hospital_number": "string",
      "first_name": "string",
      "last_name": "string",
      "middle_name": "string",
      "date_of_birth": "2026-05-09T00:00:00Z",
      "age_years": 0,
      "gender": "string",
      "blood_group": "string",
      "genotype": "string",
      "allergies": "string",
      "patient_type": "string",
      "phone_number": "string",
      "email": "string",
      "chronic_conditions": "string"
    },
    "summary": "string",
    "allergies": "string",
    "visits": [],
    "consultations": [],
    "diagnoses": [],
    "lab_orders": [],
    "radiology_orders": [],
    "prescriptions": [],
    "procedure_orders": [],
    "surgical_cases": [],
    "admissions": [],
    "triage_assessments": [],
    "vital_signs": []
  }
}
```


## 📦 Module: MEDICATION_ADHERENCE
### GET /medication-adherence/profiles
**Response Body:**
```json
[]
```

### POST /medication-adherence/profiles/from-prescription/{prescription_id}
*No specific request payload schema found.*
**Response Body:**
```json
[]
```

### POST /medication-adherence/schedules
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /medication-adherence/schedules
**Response Body:**
```json
[]
```

### POST /medication-adherence/schedules/{schedule_id}/generate-doses
*No specific request payload schema found.*
*No specific response schema found.*

### GET /medication-adherence/doses
**Response Body:**
```json
[]
```

### POST /medication-adherence/doses/{dose_id}/confirm
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /medication-adherence/patients/{patient_id}/reminder-preferences
**Response Body:**
```json
"string"
```

### PUT /medication-adherence/patients/{patient_id}/reminder-preferences
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### POST /medication-adherence/adherence/compute
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /medication-adherence/adherence/snapshots
**Response Body:**
```json
[]
```

### GET /medication-adherence/alerts
**Response Body:**
```json
[]
```

### POST /medication-adherence/alerts/{alert_id}/acknowledge
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### GET /medication-adherence/refills
*No specific response schema found.*

### POST /medication-adherence/refills/sweep-overdue
*No specific request payload schema found.*
*No specific response schema found.*

### POST /medication-adherence/follow-ups
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /medication-adherence/follow-ups
**Response Body:**
```json
[]
```

### POST /medication-adherence/follow-ups/{task_id}/complete
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```


## 📦 Module: MEMBERSHIP_CARD
### POST /
**Request Payload:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "patient_id": 0,
  "issuing_facility_id": 0,
  "initial_balance": 0.0
}
```
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z"
}
```

### GET /{card_id}
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z",
  "transactions": []
}
```

### GET /by-number/{card_number}
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z"
}
```

### GET /patient/{patient_id}
**Response Body:**
```json
[
  {
    "card_number": "string",
    "status": "string",
    "expiry_date": "2026-05-09T00:00:00Z",
    "id": 0,
    "patient_id": 0,
    "balance": 0.0,
    "issuing_facility_id": 0,
    "issued_by_id": 0,
    "date_issued": "2026-05-09T00:00:00Z"
  }
]
```

### PATCH /{card_id}
**Request Payload:**
```json
{
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z"
}
```

### POST /{card_id}/fund
**Request Payload:**
```json
{
  "amount": 0.0,
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string"
}
```
**Response Body:**
```json
{
  "amount": 0.0,
  "transaction_type": "string",
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string",
  "id": 0,
  "membership_card_id": 0,
  "patient_id": 0,
  "balance_before": 0.0,
  "balance_after": 0.0,
  "facility_id": 0,
  "processed_by_id": 0,
  "transaction_date": "2026-05-09T00:00:00Z",
  "invoice_id": 0,
  "visit_id": 0,
  "payment_id": 0
}
```

### POST /{card_id}/debit
**Request Payload:**
```json
{
  "amount": 0.0,
  "invoice_id": 0,
  "visit_id": 0,
  "narration": "string"
}
```
**Response Body:**
```json
{
  "amount": 0.0,
  "transaction_type": "string",
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string",
  "id": 0,
  "membership_card_id": 0,
  "patient_id": 0,
  "balance_before": 0.0,
  "balance_after": 0.0,
  "facility_id": 0,
  "processed_by_id": 0,
  "transaction_date": "2026-05-09T00:00:00Z",
  "invoice_id": 0,
  "visit_id": 0,
  "payment_id": 0
}
```

### GET /{card_id}/transactions
**Response Body:**
```json
[
  {
    "amount": 0.0,
    "transaction_type": "string",
    "payment_source": "string",
    "payment_reference": "string",
    "narration": "string",
    "id": 0,
    "membership_card_id": 0,
    "patient_id": 0,
    "balance_before": 0.0,
    "balance_after": 0.0,
    "facility_id": 0,
    "processed_by_id": 0,
    "transaction_date": "2026-05-09T00:00:00Z",
    "invoice_id": 0,
    "visit_id": 0,
    "payment_id": 0
  }
]
```


## 📦 Module: NOTIFICATION
### GET /notifications/templates
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /notifications/templates
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "channel": "string",
    "subject_template": "string",
    "body_template": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /notifications/templates/{template_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /notifications/templates/{template_id}
**Request Payload:**
```json
{
  "name": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "channel": "string",
    "subject_template": "string",
    "body_template": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /notifications/templates/{template_id}
*No specific response schema found.*

### GET /notifications/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /notifications/{notification_id}
**Response Body:**
```json
{
  "id": 0,
  "user_id": 0,
  "patient_id": 0,
  "template_id": 0,
  "channel": "string",
  "status": "string",
  "recipient_address": "string",
  "subject": "string",
  "body": "string",
  "payload_metadata": "string",
  "scheduled_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /notifications/dispatch
**Request Payload:**
```json
{
  "template_code": "string",
  "template_id": 0,
  "user_id": 0,
  "patient_id": 0,
  "recipient_address": "string",
  "context": "string",
  "scheduled_at": "2026-05-09T00:00:00Z",
  "channel_override": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "notification": {
    "id": 0,
    "user_id": 0,
    "patient_id": 0,
    "template_id": 0,
    "channel": "string",
    "status": "string",
    "recipient_address": "string",
    "subject": "string",
    "body": "string",
    "payload_metadata": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /notifications/dispatch-ad-hoc
**Request Payload:**
```json
{
  "channel": "string",
  "subject": "string",
  "body": "string",
  "user_id": 0,
  "patient_id": 0,
  "recipient_address": "string",
  "scheduled_at": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "notification": {
    "id": 0,
    "user_id": 0,
    "patient_id": 0,
    "template_id": 0,
    "channel": "string",
    "status": "string",
    "recipient_address": "string",
    "subject": "string",
    "body": "string",
    "payload_metadata": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /notifications/retry-failed
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "retried": 0,
  "failed": 0,
  "sent": 0
}
```

### POST /notifications/{notification_id}/mark-read
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "notification": {
    "id": 0,
    "user_id": 0,
    "patient_id": 0,
    "template_id": 0,
    "channel": "string",
    "status": "string",
    "recipient_address": "string",
    "subject": "string",
    "body": "string",
    "payload_metadata": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /notifications/messages/inbox
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /notifications/messages/sent
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /notifications/messages
**Request Payload:**
```json
{
  "recipient_user_id": 0,
  "subject": "string",
  "body": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "direct_message": {
    "id": 0,
    "sender_user_id": 0,
    "recipient_user_id": 0,
    "subject": "string",
    "body": "string",
    "status": "string",
    "sent_at": "2026-05-09T00:00:00Z",
    "read_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /notifications/messages/{message_id}/read
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "direct_message": {
    "id": 0,
    "sender_user_id": 0,
    "recipient_user_id": 0,
    "subject": "string",
    "body": "string",
    "status": "string",
    "sent_at": "2026-05-09T00:00:00Z",
    "read_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /notifications/messages/{message_id}
**Response Body:**
```json
{
  "id": 0,
  "sender_user_id": 0,
  "recipient_user_id": 0,
  "subject": "string",
  "body": "string",
  "status": "string",
  "sent_at": "2026-05-09T00:00:00Z",
  "read_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: ONBOARDING
### POST /onboarding/invitations
**Request Payload:**
```json
{
  "candidate_email": "string",
  "candidate_phone": "string",
  "notes": "string",
  "expiry_days": 0,
  "staff_profile_id": 0,
  "salary_grade_id": 0,
  "salary_step_id": 0
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /onboarding/invitations/{invitation_id}/send
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /onboarding/invitations
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /onboarding/session
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /onboarding/upload
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /onboarding/complete
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "nationality": "string",
  "address_line_1": "string",
  "city": "string",
  "state_region": "string",
  "country": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contacts": [
    {
      "full_name": "string",
      "relationship": "string",
      "phone_number": "string",
      "email": "string",
      "address": "string",
      "is_primary": false
    }
  ],
  "licenses": [
    {
      "license_type": "string",
      "license_number": "string",
      "issuing_body": "string",
      "issue_date": "2026-05-09T00:00:00Z",
      "expiry_date": "2026-05-09T00:00:00Z",
      "notes": "string"
    }
  ],
  "bank_name": "string",
  "bank_account_no": "string",
  "bank_account_name": "string"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /onboarding/progress
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /onboarding/bulk-complete
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: PATIENT_IDENTITY
### POST /patient-master/{patient_id}/identifiers
**Request Payload:**
```json
{
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /patient-master/{patient_id}/identifiers
**Response Body:**
```json
[
  {
    "id": 0,
    "patient_id": 0,
    "identifier_type": "string",
    "identifier_value": "string",
    "issuing_authority": "string",
    "is_primary": false,
    "is_active": false,
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
]
```

### POST /patient-master/{patient_id}/attachments
**Request Payload:**
```json
{
  "attachment_type": "string",
  "title": "string",
  "file_name": "string",
  "file_key": "string",
  "file_url": "string",
  "content_type": "string",
  "checksum": "string",
  "is_primary": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "uploaded_by_id": 0,
  "attachment_type": "string",
  "title": "string",
  "file_name": "string",
  "file_key": "string",
  "file_url": "string",
  "content_type": "string",
  "checksum": "string",
  "is_primary": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /patient-master/{patient_id}/consents
**Request Payload:**
```json
{
  "consent_type": "string",
  "consent_status": "string",
  "consent_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "document_file_name": "string",
  "document_file_key": "string",
  "document_file_url": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "recorded_by_id": 0,
  "consent_type": "string",
  "consent_status": "string",
  "consent_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "document_file_name": "string",
  "document_file_key": "string",
  "document_file_url": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /patient-master/insurance-providers
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "contact_person": "string",
  "email": "string",
  "phone_number": "string",
  "address": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "contact_person": "string",
  "email": "string",
  "phone_number": "string",
  "address": "string",
  "notes": "string",
  "id": 0
}
```

### GET /patient-master/insurance-providers
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "contact_person": "string",
    "email": "string",
    "phone_number": "string",
    "address": "string",
    "notes": "string",
    "id": 0
  }
]
```

### POST /patient-master/{patient_id}/insurance
**Request Payload:**
```json
{
  "insurance_provider_id": 0,
  "policy_number": "string",
  "member_name": "string",
  "relationship_to_member": "string",
  "plan_name": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "insurance_provider_id": 0,
  "policy_number": "string",
  "member_id": "string",
  "plan_name": "string",
  "coverage_details": "string",
  "status": "string",
  "valid_from": "2026-05-09T00:00:00Z",
  "valid_to": "2026-05-09T00:00:00Z",
  "note": "string",
  "insurance_provider": {
    "id": 0,
    "name": "string",
    "code": "string",
    "phone_number": "string",
    "email": "string"
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: PATIENT_PAYMENT
### GET /patient-payments/methods
**Response Body:**
```json
[]
```

### POST /patient-payments/pay
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### POST /patient-payments/confirm-gateway
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "id": 0,
  "invoice_id": 0,
  "received_by_staff_id": 0,
  "payment_reference": "string",
  "payment_method": "string",
  "payment_status": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "transaction_metadata": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: PATIENT_REGISTRATION
### POST /patient-registration/initiate-visit
**Request Payload:**
```json
{
  "existing_patient": {
    "hospital_number": "string",
    "national_identifier": "string",
    "phone_number": "string",
    "email": "string"
  },
  "new_patient": {
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "date_of_birth": "2026-05-09T00:00:00Z",
    "gender": "string",
    "marital_status": "string",
    "phone_number": "string",
    "alternate_phone_number": "string",
    "email": "string",
    "address": "string",
    "city": "string",
    "state": "string",
    "country": "string",
    "blood_group": "string",
    "genotype": "string",
    "allergies": "string",
    "emergency_contact_name": "string",
    "emergency_contact_phone": "string",
    "emergency_contact_relationship": "string",
    "next_of_kin_name": "string",
    "next_of_kin_phone": "string",
    "next_of_kin_relationship": "string",
    "next_of_kin_address": "string",
    "patient_type": "string",
    "preferred_payer_id": 0,
    "payer_type": "string",
    "national_identifier": "string",
    "national_identifier_type": "string",
    "identification_details": "string",
    "hospital_number": "string",
    "registration_notes": "string",
    "previous_identifiers": [],
    "insurance_enrollment": {
      "insurance_provider_id": 0,
      "policy_number": "string",
      "member_id": "string",
      "plan_name": "string",
      "coverage_details": "string",
      "status": "string",
      "valid_from": "2026-05-09T00:00:00Z",
      "valid_to": "2026-05-09T00:00:00Z",
      "note": "string"
    },
    "loyalty_enrollment": {
      "loyalty_program_id": 0,
      "membership_no": "string",
      "points_balance": 0.0,
      "joined_date": "2026-05-09T00:00:00Z",
      "note": "string"
    }
  },
  "options": {
    "appointment_id": 0,
    "visit_flow_template_id": 0,
    "visit_flow_template_code": "string",
    "first_service_delivery_point_id": 0,
    "use_appointment_service_point": false,
    "fast_track": false,
    "priority": "string",
    "visit_reason": "string",
    "visit_date": "2026-05-09T00:00:00Z",
    "referred_from": "string"
  },
  "admission": {
    "ward_id": 0,
    "bed_id": 0,
    "admitting_staff_id": 0,
    "admission_reason": "string",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "admitted_at": "2026-05-09T00:00:00Z",
    "capture_first_bed_day_charge": false
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "is_returning_patient": false,
  "patient_id": 0,
  "patient_hospital_number": "string",
  "visit_id": 0,
  "visit_code": "string",
  "queue_ticket_id": 0,
  "queue_number": "string",
  "queue_position": 0,
  "first_service_delivery_point_id": 0,
  "visit_flow_template_id": 0,
  "admission_id": 0,
  "admission_no": "string",
  "admission_status": "string",
  "ward_id": 0,
  "bed_id": 0,
  "bed_day_charges_captured": 0
}
```


## 📦 Module: PATIENT
### POST /patients/
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "hospital_number": "string",
  "registration_notes": "string",
  "previous_identifiers": [],
  "insurance_enrollment": {
    "insurance_provider_id": 0,
    "policy_number": "string",
    "member_id": "string",
    "plan_name": "string",
    "coverage_details": "string",
    "status": "string",
    "valid_from": "2026-05-09T00:00:00Z",
    "valid_to": "2026-05-09T00:00:00Z",
    "note": "string"
  },
  "loyalty_enrollment": {
    "loyalty_program_id": 0,
    "membership_no": "string",
    "points_balance": 0.0,
    "joined_date": "2026-05-09T00:00:00Z",
    "note": "string"
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "patient_id": 0,
  "hospital_number": "string",
  "registration_id": 0,
  "insurance_record_id": 0,
  "loyalty_membership_id": 0,
  "message": "string"
}
```

### POST /patients/duplicate-check
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "phone_number": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "national_identifier": "string",
  "previous_record_identifiers": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "possible_duplicate_found": false,
  "candidates": "2026-05-09T00:00:00Z",
  "message": "string"
}
```

### POST /patients/duplicate-review/resolve
**Request Payload:**
```json
{
  "decision": "string",
  "existing_patient_id": 0,
  "review_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "decision": "string",
  "patient_id": 0,
  "message": "string"
}
```

### POST /patients/{patient_id}/link-existing-result
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "patient_id": 0,
  "hospital_number": "string",
  "message": "string"
}
```

### POST /patients/{patient_id}/attach-insurance-later
**Request Payload:**
```json
{
  "insurance_enrollment": {
    "insurance_provider_id": 0,
    "policy_number": "string",
    "member_id": "string",
    "plan_name": "string",
    "coverage_details": "string",
    "status": "string",
    "valid_from": "2026-05-09T00:00:00Z",
    "valid_to": "2026-05-09T00:00:00Z",
    "note": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "insurance_provider_id": 0,
  "policy_number": "string",
  "member_id": "string",
  "plan_name": "string",
  "coverage_details": "string",
  "status": "string",
  "valid_from": "2026-05-09T00:00:00Z",
  "valid_to": "2026-05-09T00:00:00Z",
  "note": "string",
  "insurance_provider": {
    "id": 0,
    "name": "string",
    "code": "string",
    "phone_number": "string",
    "email": "string"
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /patients/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /patients/search
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /patients/by-hospital-number/{hospital_number}
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /patients/{patient_id}
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /patients/{patient_id}/detailed
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "insurance_records": [],
  "loyalty_memberships": [],
  "document_attachments": [],
  "consent_records": [],
  "scanned_forms": [],
  "demographic_audits": []
}
```

### PUT /patients/{patient_id}
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "insurance_records": [],
  "loyalty_memberships": [],
  "document_attachments": [],
  "consent_records": [],
  "scanned_forms": [],
  "demographic_audits": []
}
```

### POST /patients/{patient_id}/identifiers
**Request Payload:**
```json
{
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /patients/{patient_id}/photo
**Request Payload:**
```json
{
  "consent_type": "string",
  "consent_status": "string",
  "consent_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "document_file_name": "string",
  "document_file_key": "string",
  "document_file_url": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "uploaded_by_id": 0,
  "attachment_type": "string",
  "title": "string",
  "file_name": "string",
  "file_key": "string",
  "file_url": "string",
  "content_type": "string",
  "checksum": "string",
  "is_primary": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /patients/{patient_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```


## 📦 Module: PAYMENT
### GET /payments/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /payments/invoices/{invoice_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /payments/
**Request Payload:**
```json
{
  "invoice_id": 0,
  "amount": 0.0,
  "currency": "string",
  "payment_method": "string",
  "membership_card_id": 0,
  "received_by_staff_id": 0,
  "transaction_metadata": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "payment": {
    "id": 0,
    "invoice_id": 0,
    "received_by_staff_id": 0,
    "payment_reference": "string",
    "payment_method": "string",
    "payment_status": "string",
    "amount": 0.0,
    "currency": "string",
    "paid_at": "2026-05-09T00:00:00Z",
    "transaction_metadata": "string",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /payments/refund
**Request Payload:**
```json
{
  "payment_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "payment": {
    "id": 0,
    "invoice_id": 0,
    "received_by_staff_id": 0,
    "payment_reference": "string",
    "payment_method": "string",
    "payment_status": "string",
    "amount": 0.0,
    "currency": "string",
    "paid_at": "2026-05-09T00:00:00Z",
    "transaction_metadata": "string",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /payments/{payment_id}
**Response Body:**
```json
{
  "id": 0,
  "invoice_id": 0,
  "received_by_staff_id": 0,
  "payment_reference": "string",
  "payment_method": "string",
  "payment_status": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "transaction_metadata": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: PERMISSION
### GET /permissions/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /permissions/modules
*No specific response schema found.*

### GET /permissions/me
*No specific response schema found.*

### GET /permissions/{permission_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /permissions/
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /permissions/{permission_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /permissions/{permission_id}
*No specific response schema found.*

### POST /permissions/bulk-upsert
**Request Payload:**
```json
{
  "permissions": []
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "created_count": 0,
  "updated_count": 0,
  "skipped_count": 0,
  "items": []
}
```


## 📦 Module: PHARMACY
### GET /pharmacy/worklist
*No specific response schema found.*

### GET /pharmacy/stock-alerts
*No specific response schema found.*


## 📦 Module: PORTAL
### POST /portal/register
**Request Payload:**
```json
{
  "portal_username": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "patient_id": 0,
  "password": "string"
}
```
**Response Body:**
```json
{
  "portal_username": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "id": 0,
  "patient_id": 0,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z"
}
```

### POST /portal/{account_id}/appointment-requests
**Request Payload:**
```json
{
  "requested_date": "2026-05-09T00:00:00Z",
  "requested_sdp_id": 0,
  "requested_clinician_id": 0,
  "reason": "string",
  "priority": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "account_id": 0,
  "requested_date": "2026-05-09T00:00:00Z",
  "reason": "string",
  "status": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```

### POST /portal/{account_id}/messages
**Request Payload:**
```json
{
  "subject": "string",
  "body": "string",
  "parent_message_id": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "subject": "string",
  "body": "string",
  "sender_type": "string",
  "is_read": false,
  "created_at": "2026-05-09T00:00:00Z"
}
```

### POST /portal/{account_id}/document-shares
**Request Payload:**
```json
{
  "document_title": "string",
  "attachment_id": 0,
  "share_expiry": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "document_title": "string",
  "file_url": "string",
  "share_expiry": "2026-05-09T00:00:00Z",
  "is_revoked": false
}
```


## 📦 Module: PRESCRIPTION
### GET /prescriptions/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /prescriptions/
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "prescribed_by_staff_id": 0,
  "note": "string",
  "items": [],
  "auto_capture_charge": false,
  "route_to_pharmacy_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "prescription": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "prescribed_by_staff_id": 0,
    "prescription_no": "string",
    "status": "string",
    "note": "string",
    "prescribed_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /prescriptions/{prescription_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "prescribed_by_staff_id": 0,
  "prescription_no": "string",
  "status": "string",
  "note": "string",
  "prescribed_at": "2026-05-09T00:00:00Z",
  "items": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /prescriptions/{prescription_id}/cancel
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "prescription": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "prescribed_by_staff_id": 0,
    "prescription_no": "string",
    "status": "string",
    "note": "string",
    "prescribed_at": "2026-05-09T00:00:00Z",
    "items": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: PROCUREMENT
### POST /procurements/rfqs
**Request Payload:**
```json
{
  "title": "string",
  "description": "string",
  "bid_deadline": "2026-05-09T00:00:00Z",
  "vendor_ids": [
    0
  ],
  "items": [
    {
      "requisition_item_id": 0,
      "quantity": 0.0
    }
  ]
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /procurements/purchase-orders
**Request Payload:**
```json
{
  "supplier_id": 0,
  "rfq_id": 0,
  "requisition_id": 0,
  "expected_delivery_date": "2026-05-09T00:00:00Z",
  "notes": "string",
  "items": [
    {
      "item_name": "string",
      "quantity_ordered": 0.0,
      "unit_price": 0.0,
      "tax_amount": 0.0,
      "discount_amount": 0.0,
      "drug_id": 0,
      "inventory_stock_item_id": 0
    }
  ]
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /procurements/requisitions
**Request Payload:**
```json
{
  "facility_id": 0,
  "department_id": 0,
  "needed_by": "2026-05-09T00:00:00Z",
  "justification": "string",
  "requested_by_staff_id": 0,
  "items": [
    {
      "drug_id": 0,
      "inventory_stock_item_id": 0,
      "item_name": "string",
      "item_description": "string",
      "quantity_requested": 0,
      "unit_of_measure": "string",
      "estimated_unit_price": 0.0
    }
  ]
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /procurements/requisitions
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /procurements/requisitions/{requisition_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### PATCH /procurements/requisitions/{requisition_id}
**Request Payload:**
```json
{
  "facility_id": 0,
  "department_id": 0,
  "needed_by": "2026-05-09T00:00:00Z",
  "justification": "string",
  "items": [
    {
      "drug_id": 0,
      "inventory_stock_item_id": 0,
      "item_name": "string",
      "item_description": "string",
      "quantity_requested": 0,
      "unit_of_measure": "string",
      "estimated_unit_price": 0.0
    }
  ]
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### DELETE /procurements/requisitions/{requisition_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /procurements/requisitions/{requisition_id}/submit
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: PUSH_DEVICE
### POST /push-devices
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /push-devices
**Response Body:**
```json
[]
```

### DELETE /push-devices/{device_id}
*No specific response schema found.*


## 📦 Module: QUEUE
### GET /queue/my-worklist
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service_delivery_point_id": 0,
  "service_delivery_point_name": "string",
  "waiting": [],
  "serving": [],
  "served_today": 0,
  "cancelled_today": 0
}
```

### GET /queue/service-points/{service_delivery_point_id}/worklist
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service_delivery_point_id": 0,
  "service_delivery_point_name": "string",
  "waiting": [],
  "serving": [],
  "served_today": 0,
  "cancelled_today": 0
}
```

### GET /queue/service-points/{service_delivery_point_id}/tickets
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /queue/visits/{visit_id}/tickets
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /queue/tickets/{ticket_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "visit_flow_step_id": 0,
  "patient_id": 0,
  "service_delivery_point_id": 0,
  "queue_number": "string",
  "queue_position": 0,
  "status": "string",
  "called_at": "2026-05-09T00:00:00Z",
  "service_started_at": "2026-05-09T00:00:00Z",
  "service_ended_at": "2026-05-09T00:00:00Z",
  "transferred_from_ticket_id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /queue/tickets/{ticket_id}/call
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /queue/tickets/{ticket_id}/serve
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /queue/tickets/{ticket_id}/complete
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /queue/tickets/{ticket_id}/complete-and-route
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /queue/tickets/{ticket_id}/complete-and-end-visit
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### POST /queue/tickets/{ticket_id}/miss
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /queue/tickets/{ticket_id}/cancel
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /queue/tickets/{ticket_id}/transfer
**Request Payload:**
```json
{
  "target_service_delivery_point_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: REFERRAL
### GET /referrals/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0
}
```

### GET /referrals/{referral_id}
**Response Body:**
```json
{
  "id": 0,
  "referral_no": "string",
  "patient_id": 0,
  "visit_id": 0,
  "referring_staff_id": 0,
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "referral_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "date_created": "2026-05-09T00:00:00Z",
  "date_updated": "2026-05-09T00:00:00Z"
}
```

### POST /referrals/
**Request Payload:**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "referral_date": "2026-05-09T00:00:00Z",
  "priority": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "referring_staff_id": 0,
    "destination_facility": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```

### PATCH /referrals/{referral_id}
**Request Payload:**
```json
{
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "status": "string",
  "priority": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "referring_staff_id": 0,
    "destination_facility": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```

### POST /referrals/{referral_id}/cancel
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "referring_staff_id": 0,
    "destination_facility": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```

### POST /referrals/inter-facility
**Request Payload:**
```json
{
  "target_tenant_id": 0,
  "target_facility_id": 0,
  "patient_global_id": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "referral_date": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "source_tenant_id": 0,
    "source_facility_id": 0,
    "target_tenant_id": 0,
    "target_facility_id": 0,
    "patient_global_id": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "status": "string",
    "acceptance_note": "string",
    "declined_reason": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "responded_at": "2026-05-09T00:00:00Z",
    "is_history_access_granted": false,
    "access_expires_at": "2026-05-09T00:00:00Z",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```

### GET /referrals/inter-facility/incoming
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0
}
```

### POST /referrals/inter-facility/{referral_id}/respond
**Request Payload:**
```json
{
  "status": "string",
  "note": "string",
  "access_expiry_days": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "source_tenant_id": 0,
    "source_facility_id": 0,
    "target_tenant_id": 0,
    "target_facility_id": 0,
    "patient_global_id": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "status": "string",
    "acceptance_note": "string",
    "declined_reason": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "responded_at": "2026-05-09T00:00:00Z",
    "is_history_access_granted": false,
    "access_expires_at": "2026-05-09T00:00:00Z",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: REIMBURSEMENT
### POST /reimbursements
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "expense_date": "2026-05-09T00:00:00Z",
  "amount": 0.0,
  "category": "string",
  "description": "string",
  "receipt_url": "string"
}
```
**Response Body:**
```json
"string"
```

### GET /reimbursements
**Response Body:**
```json
"string"
```

### GET /reimbursements/{request_id}
**Response Body:**
```json
"string"
```

### PUT /reimbursements/{request_id}
**Request Payload:**
```json
{
  "expense_date": "2026-05-09T00:00:00Z",
  "amount": 0.0,
  "category": "string",
  "description": "string",
  "receipt_url": "string"
}
```
**Response Body:**
```json
"string"
```

### DELETE /reimbursements/{request_id}
*No specific response schema found.*

### POST /reimbursements/{request_id}/submit
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```


## 📦 Module: REPORT
### GET /reports/financial-summary
**Response Body:**
```json
{
  "total_revenue": 0.0,
  "total_invoiced": 0.0,
  "total_paid": 0.0,
  "currency": "string"
}
```

### GET /reports/operational-summary
**Response Body:**
```json
{
  "total_patients": 0,
  "total_active_visits": 0,
  "total_admissions": 0,
  "total_staff": 0
}
```

### GET /reports/platform-overview
**Response Body:**
```json
{
  "total_tenants": 0,
  "active_tenants": 0,
  "total_revenue_platform": 0.0,
  "total_api_calls": 0,
  "system_health_status": "string"
}
```


## 📦 Module: ROLE
### GET /roles/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /roles/{role_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": []
}
```

### POST /roles/
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "permission_ids": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": []
}
```

### PUT /roles/{role_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": []
}
```

### DELETE /roles/{role_id}
*No specific response schema found.*

### POST /roles/{role_id}/permissions
**Request Payload:**
```json
{
  "permission_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "role": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "permissions": []
  }
}
```

### DELETE /roles/{role_id}/permissions
**Request Payload:**
```json
{
  "permission_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "role": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "permissions": []
  }
}
```


## 📦 Module: SAAS_ADMIN_PORTAL
### GET /saas/admin/health
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /saas/admin/migrations/sync
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: SAAS_ADMIN
### GET /saas/admins
**Response Body:**
```json
[
  {
    "id": 0,
    "first_name": "string",
    "last_name": "string",
    "email": "string",
    "phone_number": "string",
    "status": "string",
    "is_superuser": false,
    "platform_role": "string"
  }
]
```

### POST /saas/admins
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "password": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```

### PUT /saas/admins/{admin_id}/status
**Request Payload:**
```json
{
  "status": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```

### GET /saas/admins/{admin_id}
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```

### PUT /saas/admins/{admin_id}
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```

### DELETE /saas/admins/{admin_id}
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: SAAS_DASHBOARD
### GET /saas/dashboard/metrics
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /saas/dashboard/overview
*No specific response schema found.*

### GET /saas/dashboard/tenants
*No specific response schema found.*

### GET /saas/dashboard/onboarding-pipeline
*No specific response schema found.*

### GET /saas/dashboard/subscriptions
*No specific response schema found.*

### GET /saas/dashboard/billing
*No specific response schema found.*

### GET /saas/dashboard/billing/ageing
*No specific response schema found.*

### GET /saas/dashboard/edge-nodes
*No specific response schema found.*

### GET /saas/dashboard/support-access
*No specific response schema found.*

### GET /saas/dashboard/usage
*No specific response schema found.*

### GET /saas/dashboard/top-tenants
*No specific response schema found.*

### GET /saas/dashboard/recent-activity
*No specific response schema found.*


## 📦 Module: SAAS_NOTIFICATION
### GET /saas/notifications
**Response Body:**
```json
{
  "key": "value"
}
```

### PATCH /saas/notifications/{notification_id}/read
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: SAAS_SUBSCRIPTION_PLAN
### GET /saas/plans
**Response Body:**
```json
[
  {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "price": 0.0,
    "currency": "string",
    "interval": 0,
    "max_facilities": 0,
    "max_users": 0,
    "max_patients": 0,
    "has_clinical": false,
    "has_inpatient": false,
    "has_laboratory": false,
    "has_pharmacy": false,
    "has_inventory": false,
    "has_billing": false,
    "has_reporting": false,
    "is_active": false
  }
]
```

### POST /saas/plans
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "price": 0.0,
  "currency": "string",
  "interval": 0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "price": 0.0,
  "currency": "string",
  "interval": 0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```

### PUT /saas/plans/{plan_id}
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "price": 0.0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "price": 0.0,
  "currency": "string",
  "interval": 0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```


## 📦 Module: SAAS_USAGE
### GET /saas/usage/{tenant_id}
**Response Body:**
```json
{
  "id": 0,
  "tenant_id": 0,
  "user_count": 0,
  "storage_usage_bytes": 0,
  "api_call_count": 0,
  "transaction_count": 0,
  "sms_count": 0,
  "email_count": 0,
  "login_count": 0,
  "last_sync_at": "2026-05-09T00:00:00Z"
}
```

### POST /saas/usage/{tenant_id}/sync
*No specific request payload schema found.*
**Response Body:**
```json
{
  "id": 0,
  "tenant_id": 0,
  "user_count": 0,
  "storage_usage_bytes": 0,
  "api_call_count": 0,
  "transaction_count": 0,
  "sms_count": 0,
  "email_count": 0,
  "login_count": 0,
  "last_sync_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: SALARY_ADVANCE
### POST /salary-advances
**Request Payload:**
```json
{
  "amount": 0.0,
  "reason": "string",
  "repayment_month": "2026-05-09T00:00:00Z",
  "staff_profile_id": 0
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /salary-advances
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /salary-advances/{request_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### PATCH /salary-advances/{request_id}
**Request Payload:**
```json
{
  "amount": 0.0,
  "reason": "string",
  "repayment_month": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### DELETE /salary-advances/{request_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /salary-advances/{request_id}/submit
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: SERVICE_DELIVERY_POINT
### POST /service-delivery-points/
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /service-delivery-points/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```

### GET /service-delivery-points/active
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```

### GET /service-delivery-points/by-code/{code}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /service-delivery-points/{service_delivery_point_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /service-delivery-points/{service_delivery_point_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PATCH /service-delivery-points/{service_delivery_point_id}/status
**Request Payload:**
```json
{
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /service-delivery-points/{service_delivery_point_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```


## 📦 Module: SHIFT
### POST /shifts/definitions
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "shift_type": "string",
  "start_time": "string",
  "end_time": "string",
  "break_duration_minutes": 0,
  "color_hex": "string",
  "description": "string",
  "department_id": 0
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /shifts/definitions
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /shifts/definitions/{definition_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### PATCH /shifts/definitions/{definition_id}
**Request Payload:**
```json
{
  "name": "string",
  "shift_type": "string",
  "start_time": "string",
  "end_time": "string",
  "break_duration_minutes": 0,
  "color_hex": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### DELETE /shifts/definitions/{definition_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /shifts/assignments
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "shift_definition_id": 0,
  "shift_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /shifts/assignments
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /shifts/assignments/{assignment_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### PATCH /shifts/assignments/{assignment_id}
**Request Payload:**
```json
{
  "shift_definition_id": 0,
  "shift_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /shifts/assignments/{assignment_id}/check-in
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /shifts/assignments/{assignment_id}/check-out
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```

### DELETE /shifts/assignments/{assignment_id}
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /shifts/swaps
**Request Payload:**
```json
{
  "requester_assignment_id": 0,
  "target_staff_id": 0,
  "target_assignment_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /shifts/swaps/{swap_id}/approve
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /shifts/swaps/{swap_id}/reject
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```


## 📦 Module: STAFF_PROFILE
### GET /staff-profiles/users
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /staff-profiles/users/{user_id}
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "password": "string",
  "role_ids": 0,
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /staff-profiles/users/{user_id}
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "status": "string",
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users/{user_id}/activate
*No specific request payload schema found.*
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users/{user_id}/deactivate
*No specific request payload schema found.*
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users/{user_id}/roles/assign
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /staff-profiles/users/{user_id}/roles
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /staff-profiles/users/{user_id}/roles
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users/{user_id}/password/reset
**Request Payload:**
```json
{
  "new_password": "string",
  "force_password_change_on_next_login": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users/me/password/change
**Request Payload:**
```json
{
  "current_password": "string",
  "new_password": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /staff-profiles/users/{user_id}/mfa
**Request Payload:**
```json
{
  "enabled": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /staff-profiles/users/{user_id}/sessions
**Response Body:**
```json
[]
```

### POST /staff-profiles/users/{user_id}/sessions/revoke
**Request Payload:**
```json
{
  "key": "value"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /staff-profiles/users/me/sessions/revoke-others
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### GET /staff-profiles/users/{user_id}/access-summary
**Response Body:**
```json
{
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  },
  "permissions": []
}
```

### GET /staff-profiles/
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /staff-profiles/{staff_profile_id}
**Response Body:**
```json
{
  "Includes": "string",
  "id": 0,
  "user_id": 0,
  "department_id": 0,
  "service_delivery_point_id": 0,
  "facility_id": 0,
  "staff_no": "string",
  "job_title": "string",
  "professional_license_no": "string",
  "specialty": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "department": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "roles": []
}
```

### GET /staff-profiles/by-user/{user_id}
**Response Body:**
```json
{
  "Includes": "string",
  "id": 0,
  "user_id": 0,
  "department_id": 0,
  "service_delivery_point_id": 0,
  "facility_id": 0,
  "staff_no": "string",
  "job_title": "string",
  "professional_license_no": "string",
  "specialty": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "department": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "roles": []
}
```

### DELETE /staff-profiles/{staff_profile_id}
**Response Body:**
```json
{
  "id": 0,
  "user_id": 0,
  "department_id": 0,
  "service_delivery_point_id": 0,
  "staff_no": "string",
  "job_title": "string",
  "professional_license_no": "string",
  "specialty": "string",
  "facility_id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: STAFF
### POST /staff/
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "password": "string",
  "role_ids": 0,
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /staff/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /staff/{user_id}
**Response Body:**
```json
{
  "Includes": "string",
  "id": 0,
  "user_id": 0,
  "department_id": 0,
  "service_delivery_point_id": 0,
  "facility_id": 0,
  "staff_no": "string",
  "job_title": "string",
  "professional_license_no": "string",
  "specialty": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "department": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "roles": []
}
```

### PATCH /staff/{user_id}
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "status": "string",
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### DELETE /staff/{staff_profile_id}
*No specific response schema found.*


## 📦 Module: STOCK_MOVEMENT
### GET /stock-movements/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /stock-movements/
**Request Payload:**
```json
{
  "store_id": 0,
  "stock_item_id": 0,
  "movement_type": "string",
  "quantity": 0.0,
  "reference_no": "string",
  "note": "string",
  "performed_by_staff_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "movement": {
    "id": 0,
    "store_id": 0,
    "stock_item_id": 0,
    "performed_by_staff_id": 0,
    "movement_type": "string",
    "reference_no": "string",
    "quantity": 0.0,
    "balance_after": 0.0,
    "movement_date": "2026-05-09T00:00:00Z",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /stock-movements/transfer
**Request Payload:**
```json
{
  "from_stock_item_id": 0,
  "to_store_id": 0,
  "quantity": 0.0,
  "note": "string",
  "performed_by_staff_id": 0
}
```
*No specific response schema found.*

### GET /stock-movements/{movement_id}
**Response Body:**
```json
{
  "id": 0,
  "store_id": 0,
  "stock_item_id": 0,
  "performed_by_staff_id": 0,
  "movement_type": "string",
  "reference_no": "string",
  "quantity": 0.0,
  "balance_after": 0.0,
  "movement_date": "2026-05-09T00:00:00Z",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```


## 📦 Module: SUBSCRIPTION_BILLING
### GET /subscription-billing/invoices
**Response Body:**
```json
[]
```

### POST /subscription-billing/invoices/issue
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "billing_id": 0,
  "payer_id": 0,
  "invoice_no": "string",
  "status": "string",
  "invoice_date": "2026-05-09T00:00:00Z",
  "due_date": "2026-05-09T00:00:00Z",
  "subtotal_amount": 0.0,
  "discount_amount": 0.0,
  "tax_amount": 0.0,
  "total_amount": 0.0,
  "amount_paid": 0.0,
  "balance_due": 0.0,
  "note": "string",
  "items": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /subscription-billing/invoices/run-due
*No specific request payload schema found.*
*No specific response schema found.*

### POST /subscription-billing/invoices/{invoice_id}/payments
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "id": 0,
  "invoice_id": 0,
  "received_by_staff_id": 0,
  "payment_reference": "string",
  "payment_method": "string",
  "payment_status": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "transaction_metadata": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```

### POST /subscription-billing/invoices/sweep-overdue
*No specific request payload schema found.*
*No specific response schema found.*

### GET /subscription-billing/invoices/me
**Response Body:**
```json
[]
```


## 📦 Module: SUPPORT_ACCESS
### POST /support-access/request
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /support-access/me
**Response Body:**
```json
[]
```

### GET /support-access
**Response Body:**
```json
[]
```

### POST /support-access/{grant_id}/approve
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### POST /support-access/{grant_id}/revoke
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### POST /support-access/sweep
*No specific request payload schema found.*
*No specific response schema found.*


## 📦 Module: TAX
### GET /tax/types
**Response Body:**
```json
[]
```

### POST /tax/types
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### PUT /tax/types/{tax_type_id}
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```

### POST /tax/rates
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /tax/rates
**Response Body:**
```json
[]
```

### POST /tax/rules
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /tax/rules
**Response Body:**
```json
[]
```

### POST /tax/exemptions
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /tax/exemptions
**Response Body:**
```json
[]
```

### POST /tax/invoices/{invoice_id}/compute
*No specific request payload schema found.*
**Response Body:**
```json
[]
```

### GET /tax/invoices/{invoice_id}/lines
**Response Body:**
```json
[]
```

### POST /tax/withholding
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /tax/withholding
**Response Body:**
```json
[]
```

### POST /tax/withholding/{record_id}/remit
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /tax/audit-log
**Response Body:**
```json
[]
```

### GET /tax/reports/summary
*No specific response schema found.*


## 📦 Module: TEMPLATE
### GET /templates/notifications
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "channel": "string",
    "subject_template": "string",
    "body_template": "string",
    "id": 0
  }
]
```

### POST /templates/notifications
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string",
  "id": 0
}
```

### GET /templates/documents
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "template_type": "string",
    "body_html": "string",
    "is_default": false,
    "id": 0
  }
]
```

### POST /templates/documents
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "template_type": "string",
  "body_html": "string",
  "is_default": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "template_type": "string",
  "body_html": "string",
  "is_default": false,
  "id": 0
}
```


## 📦 Module: TENANT_DASHBOARD
### GET /dashboard/overview
*No specific response schema found.*

### GET /dashboard/today
*No specific response schema found.*

### GET /dashboard/patients
*No specific response schema found.*

### GET /dashboard/visits
*No specific response schema found.*

### GET /dashboard/appointments
*No specific response schema found.*

### GET /dashboard/inpatient
*No specific response schema found.*

### GET /dashboard/billing
*No specific response schema found.*

### GET /dashboard/lab-pharmacy-backlog
*No specific response schema found.*

### GET /dashboard/inventory-alerts
*No specific response schema found.*

### GET /dashboard/hr
*No specific response schema found.*

### GET /dashboard/medication-adherence
*No specific response schema found.*

### GET /dashboard/recent-activity
*No specific response schema found.*


## 📦 Module: TENANT_DOMAIN
### GET /tenant-domains/{tenant_id}
**Response Body:**
```json
[]
```

### POST /tenant-domains/{tenant_id}
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### GET /tenant-domains/{tenant_id}/{domain_id}/verification
*No specific response schema found.*

### POST /tenant-domains/{tenant_id}/{domain_id}/verify
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### POST /tenant-domains/{tenant_id}/{domain_id}/make-primary
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### DELETE /tenant-domains/{tenant_id}/{domain_id}
*No specific response schema found.*

### PUT /tenant-domains/{tenant_id}/{domain_id}/ssl
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```


## 📦 Module: TENANT_EMAIL
### GET /tenant-email-config
**Response Body:**
```json
[]
```

### POST /tenant-email-config
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### PUT /tenant-email-config/{config_id}
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```

### DELETE /tenant-email-config/{config_id}
*No specific response schema found.*

### POST /tenant-email-config/{config_id}/test
*No specific request payload schema found.*
*No specific response schema found.*

### POST /tenant-email-config/{config_id}/send-test
**Request Payload:**
```json
"string"
```
*No specific response schema found.*


## 📦 Module: TENANT_JOB
### GET /tenant-jobs/handlers
*No specific response schema found.*

### GET /tenant-jobs
**Response Body:**
```json
[]
```

### POST /tenant-jobs
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### PUT /tenant-jobs/{job_id}
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```

### DELETE /tenant-jobs/{job_id}
*No specific response schema found.*


## 📦 Module: TENANT_MODULE
### GET /tenant-modules/catalog
*No specific response schema found.*

### GET /tenant-modules/{tenant_id}
**Response Body:**
```json
[]
```

### PUT /tenant-modules/{tenant_id}
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### PUT /tenant-modules/{tenant_id}/bulk
**Request Payload:**
```json
"string"
```
*No specific response schema found.*

### DELETE /tenant-modules/{tenant_id}/{module_code}
*No specific response schema found.*

### GET /tenant-modules/me/list
**Response Body:**
```json
[]
```


## 📦 Module: TENANT_PAYMENT_METHOD
### GET /tenant-payment-methods
**Response Body:**
```json
[]
```

### POST /tenant-payment-methods
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```

### PUT /tenant-payment-methods/{config_id}
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```

### DELETE /tenant-payment-methods/{config_id}
*No specific response schema found.*

### POST /tenant-payment-methods/{config_id}/test
*No specific request payload schema found.*
*No specific response schema found.*


## 📦 Module: TENANT
### POST /tenants/register
**Request Payload:**
```json
{
  "tenant_name": "string",
  "tenant_code": "string",
  "domain_url": "string",
  "billing_email": "string",
  "billing_phone": "string",
  "billing_contact_name": "string",
  "billing_address": "string",
  "tax_id": "string",
  "plan_code": "string",
  "admin_email": "string",
  "admin_username": "string",
  "admin_password": "string",
  "admin_first_name": "string",
  "admin_last_name": "string"
}
```
**Response Body:**
```json
{
  "key": "value"
}
```

### POST /tenants/{tenant_id}/approve
*No specific request payload schema found.*
**Response Body:**
```json
{
  "key": "value"
}
```

### GET /tenants
**Response Body:**
```json
{
  "total_count": 0,
  "page": 0,
  "page_size": 0,
  "tenants": [
    {
      "id": 0,
      "name": "string",
      "code": "string",
      "db_connection_string": "string",
      "status": "string",
      "domain_url": "string",
      "custom_domain": "string",
      "billing_email": "string",
      "billing_phone": "string",
      "billing_contact_name": "string",
      "billing_address": "string",
      "tax_id": "string",
      "subscriptions": [
        {
          "id": "...",
          "tenant_id": "...",
          "plan_id": "...",
          "status": "...",
          "start_date": "...",
          "end_date": "...",
          "trial_end_date": "...",
          "auto_renew": "...",
          "plan": "..."
        }
      ]
    }
  ]
}
```

### GET /tenants/{tenant_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "db_connection_string": "string",
  "status": "string",
  "domain_url": "string",
  "custom_domain": "string",
  "billing_email": "string",
  "billing_phone": "string",
  "billing_contact_name": "string",
  "billing_address": "string",
  "tax_id": "string",
  "subscriptions": [
    {
      "id": 0,
      "tenant_id": 0,
      "plan_id": 0,
      "status": "string",
      "start_date": "2026-05-09T00:00:00Z",
      "end_date": "2026-05-09T00:00:00Z",
      "trial_end_date": "2026-05-09T00:00:00Z",
      "auto_renew": false,
      "plan": {
        "id": 0,
        "name": "string",
        "code": "string",
        "description": "string",
        "price": 0.0,
        "currency": "string",
        "interval": 0,
        "max_facilities": 0,
        "max_users": 0,
        "max_patients": 0,
        "has_clinical": false,
        "has_inpatient": false,
        "has_laboratory": false,
        "has_pharmacy": false,
        "has_inventory": false,
        "has_billing": false,
        "has_reporting": false,
        "is_active": false
      }
    }
  ]
}
```

### PUT /tenants/{tenant_id}/status
**Request Payload:**
```json
{
  "status": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "db_connection_string": "string",
  "status": "string",
  "domain_url": "string",
  "custom_domain": "string",
  "billing_email": "string",
  "billing_phone": "string",
  "billing_contact_name": "string",
  "billing_address": "string",
  "tax_id": "string",
  "subscriptions": [
    {
      "id": 0,
      "tenant_id": 0,
      "plan_id": 0,
      "status": "string",
      "start_date": "2026-05-09T00:00:00Z",
      "end_date": "2026-05-09T00:00:00Z",
      "trial_end_date": "2026-05-09T00:00:00Z",
      "auto_renew": false,
      "plan": {
        "id": 0,
        "name": "string",
        "code": "string",
        "description": "string",
        "price": 0.0,
        "currency": "string",
        "interval": 0,
        "max_facilities": 0,
        "max_users": 0,
        "max_patients": 0,
        "has_clinical": false,
        "has_inpatient": false,
        "has_laboratory": false,
        "has_pharmacy": false,
        "has_inventory": false,
        "has_billing": false,
        "has_reporting": false,
        "is_active": false
      }
    }
  ]
}
```


## 📦 Module: TENANT_SETTINGS
### GET /settings
**Response Body:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```

### PUT /settings
**Request Payload:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```
**Response Body:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```

### POST /settings/logo
*No specific request payload schema found.*
**Response Body:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```


## 📦 Module: TIMESHEET
### POST /timesheets
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "period_start": "2026-05-09T00:00:00Z",
  "period_end": "2026-05-09T00:00:00Z",
  "notes": "string",
  "entries": [
    {
      "work_date": "2026-05-09T00:00:00Z",
      "regular_hours": 0.0,
      "overtime_hours": 0.0,
      "night_hours": 0.0,
      "weekend_hours": 0.0,
      "holiday_hours": 0.0,
      "is_absent": false,
      "note": "string"
    }
  ]
}
```
**Response Body:**
```json
"string"
```

### GET /timesheets
**Response Body:**
```json
"string"
```

### GET /timesheets/{timesheet_id}
**Response Body:**
```json
"string"
```

### PUT /timesheets/{timesheet_id}
**Request Payload:**
```json
{
  "notes": "string",
  "entries": [
    {
      "work_date": "2026-05-09T00:00:00Z",
      "regular_hours": 0.0,
      "overtime_hours": 0.0,
      "night_hours": 0.0,
      "weekend_hours": 0.0,
      "holiday_hours": 0.0,
      "is_absent": false,
      "note": "string"
    }
  ]
}
```
**Response Body:**
```json
"string"
```

### DELETE /timesheets/{timesheet_id}
*No specific response schema found.*

### POST /timesheets/{timesheet_id}/submit
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```


## 📦 Module: TRIAGE
### GET /triage/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /triage/
**Request Payload:**
```json
{
  "visit_id": 0,
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "assessed_by_staff_id": 0,
  "update_visit_priority": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "triage": {
    "id": 0,
    "visit_id": 0,
    "assessed_by_staff_id": 0,
    "chief_complaint": "string",
    "triage_note": "string",
    "priority": "string",
    "assessed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /triage/{triage_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "assessed_by_staff_id": 0,
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "assessed_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /triage/{triage_id}
**Request Payload:**
```json
{
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "update_visit_priority": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "triage": {
    "id": 0,
    "visit_id": 0,
    "assessed_by_staff_id": 0,
    "chief_complaint": "string",
    "triage_note": "string",
    "priority": "string",
    "assessed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: TWO_FACTOR
### GET /two-factor/challenges
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /two-factor/challenges/{challenge_id}
**Response Body:**
```json
{
  "id": 0,
  "user_id": 0,
  "challenge_type": "string",
  "purpose": "string",
  "destination": "string",
  "attempt_count": 0,
  "max_attempts": 0,
  "is_verified": false,
  "verified_at": "2026-05-09T00:00:00Z",
  "expires_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### POST /two-factor/challenges/{challenge_id}/expire
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge": {
    "id": 0,
    "user_id": 0,
    "challenge_type": "string",
    "purpose": "string",
    "destination": "string",
    "attempt_count": 0,
    "max_attempts": 0,
    "is_verified": false,
    "verified_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### POST /two-factor/users/{user_id}/expire-open-challenges
*No specific request payload schema found.*
*No specific response schema found.*

### POST /two-factor/users/{user_id}/policy
**Request Payload:**
```json
{
  "enable_two_factor": false,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user_id": 0,
  "is_two_factor_enabled": false
}
```


## 📦 Module: USER_PROFILE
### GET /users/me
**Response Body:**
```json
"string"
```

### PUT /users/me
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```

### POST /users/me/photo
*No specific request payload schema found.*
**Response Body:**
```json
"string"
```

### DELETE /users/me/photo
**Response Body:**
```json
"string"
```


## 📦 Module: USER
### GET /users
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### POST /users
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "password": "string",
  "role_ids": 0,
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/invite
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### GET /users/{user_id}
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": [],
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### PUT /users/{user_id}
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "status": "string",
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### PUT /users/{user_id}/status
**Request Payload:**
```json
{
  "status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/{user_id}/unlock
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/{user_id}/lock
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/{user_id}/deactivate
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/{user_id}/reactivate
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/{user_id}/roles
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### DELETE /users/{user_id}/roles
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### POST /users/{user_id}/password-reset
**Request Payload:**
```json
{
  "new_password": "string",
  "require_change_on_next_login": false,
  "revoke_active_sessions": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### GET /users/{user_id}/sessions
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "sessions": []
}
```

### POST /users/{user_id}/revoke-sessions
*No specific request payload schema found.*
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": [],
    "staff_profile": {
      "id": 0,
      "user_id": 0,
      "department_id": 0,
      "service_delivery_point_id": 0,
      "staff_no": "string",
      "job_title": "string",
      "professional_license_no": "string",
      "specialty": "string",
      "facility_id": 0,
      "created_at": "2026-05-09T00:00:00Z",
      "updated_at": "2026-05-09T00:00:00Z"
    }
  }
}
```

### DELETE /users/{user_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user_id": 0
}
```


## 📦 Module: VISIT_FLOW
### POST /visit-flows/templates
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /visit-flows/templates
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /visit-flows/templates/{template_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /visit-flows/templates/{template_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": [],
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /visit-flows/templates/{template_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /visit-flows/template-steps
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "template_id": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "template_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /visit-flows/template-steps/{template_step_id}
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "template_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /visit-flows/template-steps/{template_step_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /visit-flows/visit-steps
**Request Payload:**
```json
{
  "Supports": "string",
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "visit_id": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /visit-flows/visit-steps
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /visit-flows/visit-steps/{visit_step_id}
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### PUT /visit-flows/visit-steps/{visit_step_id}
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /visit-flows/visit-steps/{visit_step_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

### POST /visit-flows/combined-create
**Request Payload:**
```json
{
  "template": {
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "template_steps": [],
  "visit_id": 0,
  "visit_steps": []
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "steps": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "created_template_steps": [],
  "created_visit_steps": []
}
```


## 📦 Module: VISIT
### POST /visits/initiate
**Request Payload:**
```json
{
  "patient_id": 0,
  "appointment_id": 0,
  "visit_reason": "string",
  "referred_from": "string",
  "priority": "string",
  "status": "string",
  "first_service_delivery_point_id": 0,
  "use_appointment_service_point": false,
  "visit_flow_template_id": 0,
  "visit_date": "2026-05-09T00:00:00Z",
  "check_in_time": "2026-05-09T00:00:00Z",
  "Supports": 0,
  "create_first_flow_step": false,
  "create_queue_ticket": false,
  "first_step_status": "string",
  "first_queue_status": "string",
  "mark_visit_waiting": false,
  "fast_track": false,
  "queue_position": 0,
  "flow_step_notes": "string",
  "queue_notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "visit": {
    "id": 0,
    "patient_id": 0,
    "appointment_id": 0,
    "visit_code": "string",
    "visit_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "first_service_delivery_point_id": 0,
    "current_service_delivery_point_id": 0,
    "referred_from": "string",
    "visit_reason": "string",
    "check_in_time": "2026-05-09T00:00:00Z",
    "check_out_time": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "Includes": "string",
    "patient": {
      "id": 0,
      "hospital_number": "string",
      "first_name": "string",
      "last_name": "string",
      "middle_name": "string",
      "gender": "string",
      "phone_number": "string"
    },
    "appointment": {
      "id": 0,
      "appointment_code": "string",
      "scheduled_start_at": "2026-05-09T00:00:00Z",
      "scheduled_end_at": "2026-05-09T00:00:00Z",
      "reason": "string",
      "status": "string",
      "patient_id": 0,
      "service_delivery_point_id": 0,
      "staff_profile_id": 0
    },
    "first_service_delivery_point": {
      "id": 0,
      "name": "string",
      "code": "string",
      "service_point_type": "string",
      "department_id": 0,
      "location_description": "string",
      "queue_prefix": "string",
      "supports_appointments": false,
      "supports_walk_in": false,
      "is_active": false
    },
    "current_service_delivery_point": {
      "id": 0,
      "name": "string",
      "code": "string",
      "service_point_type": "string",
      "department_id": 0,
      "location_description": "string",
      "queue_prefix": "string",
      "supports_appointments": false,
      "supports_walk_in": false,
      "is_active": false
    },
    "flow_steps": [],
    "queue_tickets": []
  },
  "first_flow_step": {
    "id": 0,
    "visit_id": 0,
    "service_delivery_point_id": 0,
    "step_order": 0,
    "status": "string",
    "is_current": false,
    "is_required": false,
    "is_skipped": false,
    "routed_by_id": 0,
    "started_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "service_delivery_point": {
      "id": 0,
      "name": "string",
      "code": "string",
      "service_point_type": "string",
      "department_id": 0,
      "location_description": "string",
      "queue_prefix": "string",
      "supports_appointments": false,
      "supports_walk_in": false
    },
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "first_queue_ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "applied_template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "steps": [],
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "inherited_from_appointment": false,
  "fast_tracked": false
}
```

### POST /visits/{visit_id}/reroute
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "routed_by_id": 0,
  "reason": "string",
  "create_queue_ticket": false,
  "queue_status": "string",
  "queue_position": 0,
  "mark_as_current": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "visit": {
    "id": 0,
    "patient_id": 0,
    "appointment_id": 0,
    "visit_code": "string",
    "visit_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "first_service_delivery_point_id": 0,
    "current_service_delivery_point_id": 0,
    "referred_from": "string",
    "visit_reason": "string",
    "check_in_time": "2026-05-09T00:00:00Z",
    "check_out_time": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "Includes": "string",
    "patient": {
      "id": 0,
      "hospital_number": "string",
      "first_name": "string",
      "last_name": "string",
      "middle_name": "string",
      "gender": "string",
      "phone_number": "string"
    },
    "appointment": {
      "id": 0,
      "appointment_code": "string",
      "scheduled_start_at": "2026-05-09T00:00:00Z",
      "scheduled_end_at": "2026-05-09T00:00:00Z",
      "reason": "string",
      "status": "string",
      "patient_id": 0,
      "service_delivery_point_id": 0,
      "staff_profile_id": 0
    },
    "first_service_delivery_point": {
      "id": 0,
      "name": "string",
      "code": "string",
      "service_point_type": "string",
      "department_id": 0,
      "location_description": "string",
      "queue_prefix": "string",
      "supports_appointments": false,
      "supports_walk_in": false,
      "is_active": false
    },
    "current_service_delivery_point": {
      "id": 0,
      "name": "string",
      "code": "string",
      "service_point_type": "string",
      "department_id": 0,
      "location_description": "string",
      "queue_prefix": "string",
      "supports_appointments": false,
      "supports_walk_in": false,
      "is_active": false
    },
    "flow_steps": [],
    "queue_tickets": []
  },
  "new_flow_step": {
    "id": 0,
    "visit_id": 0,
    "service_delivery_point_id": 0,
    "step_order": 0,
    "status": "string",
    "is_current": false,
    "is_required": false,
    "is_skipped": false,
    "routed_by_id": 0,
    "started_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "service_delivery_point": {
      "id": 0,
      "name": "string",
      "code": "string",
      "service_point_type": "string",
      "department_id": 0,
      "location_description": "string",
      "queue_prefix": "string",
      "supports_appointments": false,
      "supports_walk_in": false
    },
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "new_queue_ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```

### GET /visits/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /visits/{visit_id}
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "appointment_id": 0,
  "visit_code": "string",
  "visit_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "referred_from": "string",
  "visit_reason": "string",
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /visits/{visit_id}/detailed
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "appointment_id": 0,
  "visit_code": "string",
  "visit_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "referred_from": "string",
  "visit_reason": "string",
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "Includes": "string",
  "patient": {
    "id": 0,
    "hospital_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "gender": "string",
    "phone_number": "string"
  },
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0
  },
  "first_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "current_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "flow_steps": [],
  "queue_tickets": []
}
```

### PUT /visits/{visit_id}
**Request Payload:**
```json
{
  "appointment_id": 0,
  "visit_reason": "string",
  "referred_from": "string",
  "priority": "string",
  "status": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "appointment_id": 0,
  "visit_code": "string",
  "visit_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "referred_from": "string",
  "visit_reason": "string",
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "Includes": "string",
  "patient": {
    "id": 0,
    "hospital_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "gender": "string",
    "phone_number": "string"
  },
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0
  },
  "first_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "current_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "flow_steps": [],
  "queue_tickets": []
}
```

### DELETE /visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```


## 📦 Module: VITAL_SIGN
### GET /vital-signs/visits/{visit_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /vital-signs/visits/{visit_id}/latest
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "recorded_by_staff_id": 0,
  "temperature_celsius": 0.0,
  "pulse_rate": 0,
  "respiratory_rate": 0,
  "systolic_bp": 0,
  "diastolic_bp": 0,
  "oxygen_saturation": 0.0,
  "weight_kg": 0.0,
  "height_cm": 0.0,
  "bmi": 0.0,
  "pain_score": 0,
  "recorded_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z"
}
```

### POST /vital-signs/
**Request Payload:**
```json
{
  "visit_id": 0,
  "recorded_by_staff_id": 0,
  "temperature_celsius": 0.0,
  "pulse_rate": 0,
  "respiratory_rate": 0,
  "systolic_bp": 0,
  "diastolic_bp": 0,
  "oxygen_saturation": 0.0,
  "weight_kg": 0.0,
  "height_cm": 0.0,
  "bmi": 0.0,
  "pain_score": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "vital_sign": {
    "id": 0,
    "visit_id": 0,
    "recorded_by_staff_id": 0,
    "temperature_celsius": 0.0,
    "pulse_rate": 0,
    "respiratory_rate": 0,
    "systolic_bp": 0,
    "diastolic_bp": 0,
    "oxygen_saturation": 0.0,
    "weight_kg": 0.0,
    "height_cm": 0.0,
    "bmi": 0.0,
    "pain_score": 0,
    "recorded_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```


## 📦 Module: WARD
### POST /wards/
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "Args": "string",
  "Returns": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /wards/
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": [],
  "count": 0,
  "meta": {
    "key": "value"
  }
}
```

### GET /wards/{ward_id}
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### GET /wards/{ward_id}/summary
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "total_beds": 0,
  "available_beds": 0,
  "occupied_beds": 0,
  "total_admissions": 0,
  "active_admissions": 0
}
```

### PUT /wards/{ward_id}
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```

### DELETE /wards/{ward_id}
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```

