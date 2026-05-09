# Carepoint HMS — UI to API Mapping Reference

This document maps each UI Page/Feature to its required API endpoints, including sample payloads for the frontend team.

## 📦 Module: ADMISSION
### GET /admissions/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /admissions/wards/{ward_id}/active
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /admissions/{admission_id}
**Response Body (JSON):**
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
---

### POST /admissions/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /admissions/from-visit
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /admissions/{admission_id}/transfer
**Request Payload (JSON):**
```json
{
  "new_bed_id": 0,
  "new_ward_id": 0,
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### POST /admissions/{admission_id}/status
**Request Payload (JSON):**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### POST /admissions/{admission_id}/bed-days
**Request Payload (JSON):**
```json
{
  "through_date": "2026-05-09T00:00:00Z"
}
```
**Response Body (JSON):**
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
---

## 📦 Module: AMBULANCE
### GET /ambulances/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /ambulances/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /ambulances/{ambulance_id}
**Response Body (JSON):**
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
---

### PUT /ambulances/{ambulance_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /ambulances/{ambulance_id}/status
**Request Payload (JSON):**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /ambulances/{ambulance_id}
---

### GET /ambulances/{ambulance_id}/readiness
**Response Body (JSON):**
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
---

### GET /ambulances/drivers/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /ambulances/drivers/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /ambulances/drivers/{driver_id}
**Request Payload (JSON):**
```json
{
  "license_expiry_date": "2026-05-09T00:00:00Z",
  "is_primary_driver": false,
  "emergency_response_certified": false,
  "ambulance_id": 0,
  "notes": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /ambulances/drivers/{driver_id}
---

### GET /ambulances/{ambulance_id}/equipment
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /ambulances/{ambulance_id}/equipment
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /ambulances/equipment/{equipment_id}
**Request Payload (JSON):**
```json
{
  "equipment_name": "string",
  "quantity": 0.0,
  "condition_status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /ambulances/equipment/{equipment_id}
---

### GET /ambulances/{ambulance_id}/maintenance
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

### POST /ambulances/{ambulance_id}/maintenance
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /ambulances/maintenance/{maintenance_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

## 📦 Module: APPOINTMENT_EXTENSION
### POST /appointment-scheduling/reminders/schedule
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /appointment-scheduling/reminders/dispatch-due
---

### POST /appointment-scheduling/history/{appointment_id}/log
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /appointment-scheduling/history/{appointment_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /appointment-scheduling/recurrence
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /appointment-scheduling/recurrence/{rule_id}/expand
---

## 📦 Module: APPOINTMENT
### GET /appointments/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

### GET /appointments/arrival-board
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

### GET /appointments/availability
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "available": false,
  "conflicts": 0
}
```
---

### GET /appointments/{appointment_id}
**Response Body (JSON):**
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
---

### POST /appointments/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /appointments/{appointment_id}/reschedule
**Request Payload (JSON):**
```json
{
  "new_scheduled_start_at": "2026-05-09T00:00:00Z",
  "new_scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### POST /appointments/{appointment_id}/cancel
**Request Payload (JSON):**
```json
{
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### POST /appointments/{appointment_id}/no-show
**Request Payload (JSON):**
```json
{
  "note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /appointments/{appointment_id}/check-in
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

## 📦 Module: APPROVAL
### GET /approvals/flows
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /approvals/flows
**Request Payload (JSON):**
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
  "steps": "string"
}
```
**Response Body (JSON):**
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
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /approvals/flows/{flow_id}
**Response Body (JSON):**
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
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### PATCH /approvals/flows/{flow_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### DELETE /approvals/flows/{flow_id}
**Response Body (JSON):**
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
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /approvals/requests
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /approvals/requests/inbox
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /approvals/requests/mine
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /approvals/requests
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /approvals/requests/{request_id}
**Response Body (JSON):**
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
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /approvals/requests/{request_id}/decisions
**Request Payload (JSON):**
```json
{
  "action": "string",
  "comment": "string",
  "delegated_to_user_id": 0,
  "step_id": 0
}
```
**Response Body (JSON):**
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
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /approvals/requests/{request_id}/comments
**Request Payload (JSON):**
```json
{
  "body": "string"
}
```
**Response Body (JSON):**
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
---

### POST /approvals/requests/{request_id}/cancel
**Response Body (JSON):**
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
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /approvals/requests/{request_id}/force-close
**Response Body (JSON):**
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
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /approvals/requests/{request_id}/steps/{step_id}/reopen
**Response Body (JSON):**
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
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /approvals/maintenance/expire-stale
---

## 📦 Module: AUTH
### POST /auth/login
**Request Payload (JSON):**
```json
{
  "identifier": "string",
  "password": "string",
  "remember_me": false
}
```
**Response Body (JSON):**
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
---

### POST /auth/refresh
**Request Payload (JSON):**
```json
{
  "refresh_token": "string"
}
```
**Response Body (JSON):**
```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": 0
}
```
---

### POST /auth/impersonate
**Request Payload (JSON):**
```json
{
  "tenant_code": "string"
}
```
**Response Body (JSON):**
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
---

### POST /auth/logout
**Request Payload (JSON):**
```json
{
  "refresh_token": "string",
  "all_sessions": false
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### GET /auth/me
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /auth/change-password
**Request Payload (JSON):**
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_new_password": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /auth/forgot-password
**Request Payload (JSON):**
```json
{
  "identifier": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /auth/reset-password
**Request Payload (JSON):**
```json
{
  "reset_token": "string",
  "new_password": "string",
  "confirm_new_password": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /auth/otp/verify
**Request Payload (JSON):**
```json
{
  "user_id": 0,
  "identifier": "string",
  "otp_code": "string",
  "challenge_reference": "string",
  "purpose": "string"
}
```
**Response Body (JSON):**
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
---

### POST /auth/otp/resend
**Request Payload (JSON):**
```json
{
  "user_id": 0,
  "identifier": "string",
  "purpose": "string",
  "delivery_method": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```
---

### POST /auth/two-factor/setup
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /auth/two-factor/verify
**Request Payload (JSON):**
```json
{
  "user_id": 0,
  "identifier": "string",
  "otp_code": "string",
  "method": "string",
  "challenge_reference": "string"
}
```
**Response Body (JSON):**
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
---

### POST /auth/email-verification/request
**Request Payload (JSON):**
```json
{
  "user_id": 0,
  "email": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```
---

### POST /auth/email-verification/confirm
**Request Payload (JSON):**
```json
{
  "token": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /auth/phone-verification/request
**Request Payload (JSON):**
```json
{
  "user_id": 0,
  "phone_number": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```
---

### POST /auth/phone-verification/confirm
**Request Payload (JSON):**
```json
{
  "token": "string",
  "otp_code": "string",
  "challenge_reference": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

## 📦 Module: BED
### POST /beds/
**Request Payload (JSON):**
```json
{
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string"
}
```
**Response Body (JSON):**
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
---

### GET /beds/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /beds/{bed_id}
**Response Body (JSON):**
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
---

### GET /beds/{bed_id}/summary
**Response Body (JSON):**
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
---

### PUT /beds/{bed_id}
**Request Payload (JSON):**
```json
{
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /beds/{bed_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

## 📦 Module: BILLING
### GET /billing/services
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /billing/services
**Request Payload (JSON):**
```json
{
  "code": "string",
  "name": "string",
  "category": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### PUT /billing/services/{sid}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "category": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /billing/services/{sid}
---

### GET /billing/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /billing/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /billing/
**Request Payload (JSON):**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "patient_insurance_id": 0,
  "notes": "string",
  "items": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /billing/{billing_id}
**Response Body (JSON):**
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
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### POST /billing/{billing_id}/items
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /billing/{billing_id}/cancel
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

## 📦 Module: CLINICIAN
### GET /clinicians/
---

## 📦 Module: COMPLIANCE
### GET /compliance/records
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /compliance/records
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /compliance/records/{record_id}
**Response Body (JSON):**
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
---

### PUT /compliance/records/{record_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /compliance/records/{record_id}
---

### GET /compliance/accreditations
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /compliance/accreditations
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /compliance/accreditations/{accreditation_id}
**Response Body (JSON):**
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
---

### PUT /compliance/accreditations/{accreditation_id}
**Request Payload (JSON):**
```json
{
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /compliance/accreditations/{accreditation_id}
---

### GET /compliance/incidents
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /compliance/incidents
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /compliance/incidents/{incident_id}
**Response Body (JSON):**
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
---

### PUT /compliance/incidents/{incident_id}
**Request Payload (JSON):**
```json
{
  "severity": "string",
  "category": "string",
  "immediate_action_taken": "string",
  "follow_up_required": false
}
```
**Response Body (JSON):**
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
---

### GET /compliance/infection-logs
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /compliance/infection-logs
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /compliance/infection-logs/{log_id}
**Response Body (JSON):**
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
---

### GET /compliance/quality-projects
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /compliance/quality-projects
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /compliance/quality-projects/{project_id}
**Response Body (JSON):**
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
---

### PUT /compliance/quality-projects/{project_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /compliance/dashboard
**Response Body (JSON):**
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
---

## 📦 Module: CONSULTATION
### GET /consultations/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /consultations/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /consultations/{consultation_id}
**Response Body (JSON):**
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
---

### PUT /consultations/{consultation_id}
**Request Payload (JSON):**
```json
{
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /consultations/{consultation_id}/finalize
**Request Payload (JSON):**
```json
{
  "next_service_delivery_point_id": 0,
  "end_visit": false,
  "closing_note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /consultations/{consultation_id}/cancel
**Response Body (JSON):**
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
---

## 📦 Module: DATABASE_BACKUP
### GET /backups
**Response Body (JSON):**
```json
"string"
```
---

### POST /backups
**Response Body (JSON):**
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
---

### GET /backups/{backup_id}/download
---

### POST /backups/{backup_id}/restore
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /backups/retention/sweep
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: DEPARTMENT
### POST /departments/
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false
}
```
**Response Body (JSON):**
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
---

### GET /departments/
**Response Body (JSON):**
```json
{
  "success": false,
  "items": "string",
  "count": 0
}
```
---

### GET /departments/{department_id}
**Response Body (JSON):**
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
---

### PATCH /departments/{department_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false
}
```
**Response Body (JSON):**
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
---

### DELETE /departments/{department_id}
---

## 📦 Module: DIAGNOSIS
### GET /diagnoses/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /diagnoses/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /diagnoses/{diagnosis_id}
**Response Body (JSON):**
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
---

### PUT /diagnoses/{diagnosis_id}
**Request Payload (JSON):**
```json
{
  "diagnosis_name": "string",
  "diagnosis_code": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string"
}
```
**Response Body (JSON):**
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
---

## 📦 Module: DISCHARGE
### POST /discharges/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /discharges/admissions/{admission_id}/readiness
---

### GET /discharges/{discharge_id}
**Response Body (JSON):**
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
---

### GET /discharges/admissions/{admission_id}
**Response Body (JSON):**
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
---

## 📦 Module: DISPENSE
### POST /dispenses/
**Request Payload (JSON):**
```json
{
  "prescription_id": 0,
  "dispensed_by_staff_id": 0,
  "note": "string",
  "items": "string",
  "store_id": 0
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /dispenses/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /dispenses/prescriptions/{prescription_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /dispenses/{dispense_id}
**Response Body (JSON):**
```json
{
  "id": 0,
  "prescription_id": 0,
  "dispensed_by_staff_id": 0,
  "dispense_no": "string",
  "status": "string",
  "dispensed_at": "2026-05-09T00:00:00Z",
  "note": "string",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

## 📦 Module: DOCTOR_CALENDAR
### GET /doctor-calendar/templates
**Response Body (JSON):**
```json
"string"
```
---

### POST /doctor-calendar/templates
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /doctor-calendar/templates/{template_id}/deactivate
**Response Body (JSON):**
```json
"string"
```
---

### POST /doctor-calendar/time-off
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /doctor-calendar/slots/materialise
**Request Payload (JSON):**
```json
"string"
```
---

### GET /doctor-calendar/slots
**Response Body (JSON):**
```json
"string"
```
---

### GET /doctor-calendar/workload/{staff_profile_id}
---

### POST /doctor-calendar/slots/{slot_id}/reserve
**Response Body (JSON):**
```json
"string"
```
---

### POST /doctor-calendar/slots/{slot_id}/release
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: DRUG
### GET /drugs/categories
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /drugs/categories
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### PUT /drugs/categories/{cat_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /drugs/categories/{cat_id}
---

### GET /drugs/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /drugs/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /drugs/{drug_id}
**Response Body (JSON):**
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
---

### PUT /drugs/{drug_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /drugs/{drug_id}
---

## 📦 Module: EDGE_NODE
## 📦 Module: FACILITY
### GET /facilities
**Response Body (JSON):**
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
        "area_name": "...",
        "region_code": "...",
        "notes": "...",
        "id": "...",
        "facility_id": "..."
      }
    ]
  }
]
```
---

### GET /facilities/{facility_id}
**Response Body (JSON):**
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
---

### POST /facilities
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /facilities/{facility_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /facilities/{facility_id}
---

### GET /facilities/networks/all
**Response Body (JSON):**
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
---

### POST /facilities/networks/create
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "head_office_facility_id": 0
}
```
**Response Body (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0,
  "head_office_facility_id": 0
}
```
---

### PUT /facilities/networks/{network_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "description": "string",
  "head_office_facility_id": 0
}
```
**Response Body (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0,
  "head_office_facility_id": 0
}
```
---

### DELETE /facilities/networks/{network_id}
---

### GET /facilities/service-areas/all
**Response Body (JSON):**
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
---

### POST /facilities/service-areas/create
**Request Payload (JSON):**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "facility_id": 0
}
```
**Response Body (JSON):**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "id": 0,
  "facility_id": 0
}
```
---

### PUT /facilities/service-areas/{area_id}
**Request Payload (JSON):**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string"
}
```
**Response Body (JSON):**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "id": 0,
  "facility_id": 0
}
```
---

### DELETE /facilities/service-areas/{area_id}
---

## 📦 Module: HR_PAYROLL
### POST /hr/payroll-config/allowance-types
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /hr/payroll-config/allowance-types
**Response Body (JSON):**
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
---

### POST /hr/payroll-config/deduction-types
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /hr/payroll-config/deduction-types
**Response Body (JSON):**
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
---

### POST /hr/payroll-config/statutory-configs
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /hr/payroll-config/statutory-configs
**Response Body (JSON):**
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
---

## 📦 Module: HR
### POST /hr/onboarding/{staff_profile_id}/seed
---

### POST /hr/onboarding/items/{item_id}/complete
---

### POST /hr/offboarding/{staff_profile_id}/seed
---

### POST /hr/offboarding/items/{item_id}/complete
---

### POST /hr/profiles/{staff_profile_id}/status
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/profiles/{staff_profile_id}/status-history
---

### POST /hr/contracts
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/contracts
---

### POST /hr/documents
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/documents
---

### POST /hr/licenses
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/licenses
---

### POST /hr/licenses/sweep-expiries
---

### POST /hr/roster/shift-templates
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/roster/shift-templates
---

### POST /hr/roster/rosters
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/roster/assignments
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/roster/assignments/{assignment_id}/swap
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/roster/assignments
---

### POST /hr/attendance/clock-in
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/attendance/clock-out
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/attendance
---

### POST /hr/timesheets/generate
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/timesheets/{timesheet_id}/submit
---

### POST /hr/timesheets/{timesheet_id}/approve
---

### POST /hr/timesheets/{timesheet_id}/lock
---

### GET /hr/timesheets
---

### POST /hr/leave/types
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/leave/types
---

### POST /hr/leave/requests
**Request Payload (JSON):**
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
---

### POST /hr/leave/requests/{request_id}/decide
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/leave/requests
---

### GET /hr/leave/balances
---

### POST /hr/leave/holidays
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/leave/holidays
---

### POST /hr/payroll/runs
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/payroll/runs/{run_id}/calculate
---

### POST /hr/payroll/runs/{run_id}/approve
---

### POST /hr/payroll/runs/{run_id}/lock
---

### GET /hr/payroll/runs
---

### GET /hr/payroll/runs/{run_id}/lines
---

### POST /hr/overtime
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/overtime/{record_id}/decide
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/loans
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/loans/{loan_id}/approve
---

### POST /hr/loans/{loan_id}/repay
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/payroll/salary
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/tasks
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/tasks
---

### POST /hr/announcements
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/announcements
---

### POST /hr/incidents
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/incidents/actions
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/requests
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/requests/{request_id}/decide
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/appraisals/cycles
**Request Payload (JSON):**
```json
"string"
```
---

### POST /hr/training/records
**Request Payload (JSON):**
```json
"string"
```
---

### GET /hr/reports/headcount
---

### GET /hr/audit-log
---

## 📦 Module: INSURANCE_CLAIM
## 📦 Module: INTEGRATION
### GET /integrations/
**Response Body (JSON):**
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
        "credential_type": "...",
        "secret_reference": "...",
        "id": "..."
      }
    ]
  }
]
```
---

### POST /integrations/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /integrations/{endpoint_id}
**Response Body (JSON):**
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
---

### PUT /integrations/{endpoint_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /integrations/{endpoint_id}
---

## 📦 Module: INVENTORY
### GET /inventory/stores
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /inventory/stores
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "location_description": "string",
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### GET /inventory/stores/{store_id}
**Response Body (JSON):**
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
---

### PUT /inventory/stores/{store_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "location_description": "string",
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /inventory/stores/{store_id}
---

### GET /inventory/items
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /inventory/items
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /inventory/items/{item_id}
**Response Body (JSON):**
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
---

### PUT /inventory/items/{item_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /inventory/items/{item_id}
---

### GET /inventory/movements
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /inventory/movements
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /inventory/movements/{movement_id}
**Response Body (JSON):**
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
---

## 📦 Module: INVITATION
### POST /invitations
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /invitations
**Response Body (JSON):**
```json
"string"
```
---

### POST /invitations/{invitation_id}/cancel
**Response Body (JSON):**
```json
"string"
```
---

### POST /invitations/{invitation_id}/resend
**Response Body (JSON):**
```json
"string"
```
---

### POST /invitations/sweep
---

### POST /invitations/accept
**Request Payload (JSON):**
```json
"string"
```
---

## 📦 Module: INVOICE
### GET /invoices/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /invoices/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /invoices/issue-from-billing
**Request Payload (JSON):**
```json
{
  "billing_id": 0,
  "payer_id": 0,
  "due_date": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /invoices/{invoice_id}
**Response Body (JSON):**
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
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### POST /invoices/{invoice_id}/void
**Request Payload (JSON):**
```json
{
  "reason": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

## 📦 Module: LAB_ORDER
### GET /lab/orders/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /lab/orders/worklist
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /lab/orders/
**Request Payload (JSON):**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "clinical_note": "string",
  "items": "string",
  "auto_capture_charge": false,
  "route_to_lab_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /lab/orders/{order_id}
**Response Body (JSON):**
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
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### POST /lab/orders/items/{item_id}/collect-specimen
**Request Payload (JSON):**
```json
{
  "specimen_id": "string",
  "collected_by_staff_id": 0,
  "note": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /lab/orders/items/{item_id}/start-processing
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /lab/orders/items/{item_id}/cancel
**Request Payload (JSON):**
```json
{
  "reason": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### POST /lab/orders/{order_id}/cancel
**Request Payload (JSON):**
```json
{
  "reason": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

## 📦 Module: LAB_RESULT
### POST /lab/results/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /lab/results/{result_id}
**Request Payload (JSON):**
```json
{
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string"
}
```
**Response Body (JSON):**
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
---

### POST /lab/results/{result_id}/verify
**Request Payload (JSON):**
```json
{
  "verified_by_staff_id": 0,
  "verification_note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /lab/results/{result_id}/release
**Request Payload (JSON):**
```json
{
  "release_note": "string",
  "notify_clinician": false,
  "route_to_service_delivery_point_id": 0
}
```
**Response Body (JSON):**
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
---

### POST /lab/results/{result_id}/cancel
**Response Body (JSON):**
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
---

### GET /lab/results/{result_id}
**Response Body (JSON):**
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
---

### GET /lab/results/by-item/{item_id}
**Response Body (JSON):**
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
---

## 📦 Module: LAB
### GET /lab/tests/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /lab/tests/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /lab/tests/{test_id}
**Response Body (JSON):**
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
---

### PUT /lab/tests/{test_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /lab/tests/{test_id}
---

## 📦 Module: LEAVE_REQUEST
### POST /leave-requests
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### GET /leave-requests
**Response Body (JSON):**
```json
"string"
```
---

### GET /leave-requests/{request_id}
**Response Body (JSON):**
```json
"string"
```
---

### PUT /leave-requests/{request_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /leave-requests/{request_id}
---

### POST /leave-requests/{request_id}/submit
**Request Payload (JSON):**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: LOYALTY
### POST /loyalty-network/programs
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /loyalty-network/programs
**Response Body (JSON):**
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
---

### POST /loyalty-network/networks
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0
}
```
---

### GET /loyalty-network/networks
**Response Body (JSON):**
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
---

## 📦 Module: MEDICAL_HISTORY
### GET /patients/{patient_id}/medical-history
**Response Body (JSON):**
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
    "visits": "string",
    "consultations": "string",
    "diagnoses": "string",
    "lab_orders": "string",
    "radiology_orders": "string",
    "prescriptions": "string",
    "procedure_orders": "string",
    "surgical_cases": "string",
    "admissions": "string",
    "triage_assessments": "string",
    "vital_signs": "string"
  }
}
```
---

### GET /visits/{visit_id}/medical-history
**Response Body (JSON):**
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
    "visits": "string",
    "consultations": "string",
    "diagnoses": "string",
    "lab_orders": "string",
    "radiology_orders": "string",
    "prescriptions": "string",
    "procedure_orders": "string",
    "surgical_cases": "string",
    "admissions": "string",
    "triage_assessments": "string",
    "vital_signs": "string"
  }
}
```
---

## 📦 Module: MEDICATION_ADHERENCE
### GET /medication-adherence/profiles
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/profiles/from-prescription/{prescription_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/schedules
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /medication-adherence/schedules
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/schedules/{schedule_id}/generate-doses
---

### GET /medication-adherence/doses
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/doses/{dose_id}/confirm
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /medication-adherence/patients/{patient_id}/reminder-preferences
**Response Body (JSON):**
```json
"string"
```
---

### PUT /medication-adherence/patients/{patient_id}/reminder-preferences
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/adherence/compute
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /medication-adherence/adherence/snapshots
**Response Body (JSON):**
```json
"string"
```
---

### GET /medication-adherence/alerts
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/alerts/{alert_id}/acknowledge
**Response Body (JSON):**
```json
"string"
```
---

### GET /medication-adherence/refills
---

### POST /medication-adherence/refills/sweep-overdue
---

### POST /medication-adherence/follow-ups
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /medication-adherence/follow-ups
**Response Body (JSON):**
```json
"string"
```
---

### POST /medication-adherence/follow-ups/{task_id}/complete
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: MEMBERSHIP_CARD
### POST /
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /{card_id}
**Response Body (JSON):**
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
  "transactions": "string"
}
```
---

### GET /by-number/{card_number}
**Response Body (JSON):**
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
---

### GET /patient/{patient_id}
**Response Body (JSON):**
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
---

### PATCH /{card_id}
**Request Payload (JSON):**
```json
{
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z"
}
```
**Response Body (JSON):**
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
---

### POST /{card_id}/fund
**Request Payload (JSON):**
```json
{
  "amount": 0.0,
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string"
}
```
**Response Body (JSON):**
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
---

### POST /{card_id}/debit
**Request Payload (JSON):**
```json
{
  "amount": 0.0,
  "invoice_id": 0,
  "visit_id": 0,
  "narration": "string"
}
```
**Response Body (JSON):**
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
---

### GET /{card_id}/transactions
**Response Body (JSON):**
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
---

## 📦 Module: NOTIFICATION
### GET /notifications/templates
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /notifications/templates
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body (JSON):**
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
---

### GET /notifications/templates/{template_id}
**Response Body (JSON):**
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
---

### PUT /notifications/templates/{template_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /notifications/templates/{template_id}
---

### GET /notifications/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /notifications/{notification_id}
**Response Body (JSON):**
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
---

### POST /notifications/dispatch
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /notifications/dispatch-ad-hoc
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /notifications/retry-failed
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "retried": 0,
  "failed": 0,
  "sent": 0
}
```
---

### POST /notifications/{notification_id}/mark-read
**Response Body (JSON):**
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
---

### GET /notifications/messages/inbox
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /notifications/messages/sent
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /notifications/messages
**Request Payload (JSON):**
```json
{
  "recipient_user_id": 0,
  "subject": "string",
  "body": "string"
}
```
**Response Body (JSON):**
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
---

### POST /notifications/messages/{message_id}/read
**Response Body (JSON):**
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
---

### GET /notifications/messages/{message_id}
**Response Body (JSON):**
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
---

## 📦 Module: ONBOARDING
### POST /onboarding/invitations
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### POST /onboarding/invitations/{invitation_id}/send
**Response Body (JSON):**
```json
"string"
```
---

### GET /onboarding/invitations
**Response Body (JSON):**
```json
"string"
```
---

### GET /onboarding/session
**Response Body (JSON):**
```json
"string"
```
---

### POST /onboarding/upload
**Response Body (JSON):**
```json
"string"
```
---

### POST /onboarding/complete
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### GET /onboarding/progress
**Response Body (JSON):**
```json
"string"
```
---

### POST /onboarding/bulk-complete
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: PATIENT_IDENTITY
### POST /patient-master/{patient_id}/identifiers
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /patient-master/{patient_id}/identifiers
**Response Body (JSON):**
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
---

### POST /patient-master/{patient_id}/attachments
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /patient-master/{patient_id}/consents
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /patient-master/insurance-providers
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /patient-master/insurance-providers
**Response Body (JSON):**
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
---

### POST /patient-master/{patient_id}/insurance
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

## 📦 Module: PATIENT_PAYMENT
### GET /patient-payments/methods
**Response Body (JSON):**
```json
"string"
```
---

### POST /patient-payments/pay
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /patient-payments/confirm-gateway
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
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
---

## 📦 Module: PATIENT_PORTAL
## 📦 Module: PATIENT_REGISTRATION
### POST /patient-registration/initiate-visit
**Request Payload (JSON):**
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
    "previous_identifiers": "string",
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
**Response Body (JSON):**
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
---

## 📦 Module: PATIENT
### POST /patients/
**Request Payload (JSON):**
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
  "previous_identifiers": "string",
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
**Response Body (JSON):**
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
---

### POST /patients/duplicate-check
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
{
  "success": false,
  "possible_duplicate_found": false,
  "candidates": "2026-05-09T00:00:00Z",
  "message": "string"
}
```
---

### POST /patients/duplicate-review/resolve
**Request Payload (JSON):**
```json
{
  "decision": "string",
  "existing_patient_id": 0,
  "review_note": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "decision": "string",
  "patient_id": 0,
  "message": "string"
}
```
---

### POST /patients/{patient_id}/link-existing-result
**Response Body (JSON):**
```json
{
  "success": false,
  "patient_id": 0,
  "hospital_number": "string",
  "message": "string"
}
```
---

### POST /patients/{patient_id}/attach-insurance-later
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /patients/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /patients/search
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /patients/by-hospital-number/{hospital_number}
**Response Body (JSON):**
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
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### GET /patients/{patient_id}
**Response Body (JSON):**
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
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### GET /patients/{patient_id}/detailed
**Response Body (JSON):**
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
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "insurance_records": "string",
  "loyalty_memberships": "string",
  "document_attachments": "string",
  "consent_records": "string",
  "scanned_forms": "string",
  "demographic_audits": "string"
}
```
---

### PUT /patients/{patient_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "insurance_records": "string",
  "loyalty_memberships": "string",
  "document_attachments": "string",
  "consent_records": "string",
  "scanned_forms": "string",
  "demographic_audits": "string"
}
```
---

### POST /patients/{patient_id}/identifiers
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /patients/{patient_id}/photo
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /patients/{patient_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

## 📦 Module: PAYMENT
### GET /payments/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /payments/invoices/{invoice_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /payments/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /payments/refund
**Request Payload (JSON):**
```json
{
  "payment_id": 0,
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### GET /payments/{payment_id}
**Response Body (JSON):**
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
---

## 📦 Module: PAYSTACK_WEBHOOK
## 📦 Module: PERMISSION
### GET /permissions/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /permissions/modules
---

### GET /permissions/me
---

### GET /permissions/{permission_id}
**Response Body (JSON):**
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
---

### POST /permissions/
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false
}
```
**Response Body (JSON):**
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
---

### PUT /permissions/{permission_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /permissions/{permission_id}
---

### POST /permissions/bulk-upsert
**Request Payload (JSON):**
```json
{
  "permissions": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "created_count": 0,
  "updated_count": 0,
  "skipped_count": 0,
  "items": "string"
}
```
---

## 📦 Module: PHARMACY
### GET /pharmacy/worklist
---

### GET /pharmacy/stock-alerts
---

## 📦 Module: PORTAL
### POST /portal/register
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /portal/{account_id}/appointment-requests
**Request Payload (JSON):**
```json
{
  "requested_date": "2026-05-09T00:00:00Z",
  "requested_sdp_id": 0,
  "requested_clinician_id": 0,
  "reason": "string",
  "priority": "string"
}
```
**Response Body (JSON):**
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
---

### POST /portal/{account_id}/messages
**Request Payload (JSON):**
```json
{
  "subject": "string",
  "body": "string",
  "parent_message_id": 0
}
```
**Response Body (JSON):**
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
---

### POST /portal/{account_id}/document-shares
**Request Payload (JSON):**
```json
{
  "document_title": "string",
  "attachment_id": 0,
  "share_expiry": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body (JSON):**
```json
{
  "id": 0,
  "document_title": "string",
  "file_url": "string",
  "share_expiry": "2026-05-09T00:00:00Z",
  "is_revoked": false
}
```
---

## 📦 Module: PRESCRIPTION
### GET /prescriptions/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /prescriptions/
**Request Payload (JSON):**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "prescribed_by_staff_id": 0,
  "note": "string",
  "items": "string",
  "auto_capture_charge": false,
  "route_to_pharmacy_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

### GET /prescriptions/{prescription_id}
**Response Body (JSON):**
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
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### POST /prescriptions/{prescription_id}/cancel
**Request Payload (JSON):**
```json
{
  "reason": "string"
}
```
**Response Body (JSON):**
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
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

## 📦 Module: PROCEDURE
## 📦 Module: PROCUREMENT
### POST /procurements/rfqs
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### POST /procurements/purchase-orders
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### POST /procurements/requisitions
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### GET /procurements/requisitions
**Response Body (JSON):**
```json
"string"
```
---

### GET /procurements/requisitions/{requisition_id}
**Response Body (JSON):**
```json
"string"
```
---

### PATCH /procurements/requisitions/{requisition_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /procurements/requisitions/{requisition_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /procurements/requisitions/{requisition_id}/submit
**Request Payload (JSON):**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: PUSH_DEVICE
### POST /push-devices
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /push-devices
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /push-devices/{device_id}
---

## 📦 Module: QUEUE
### GET /queue/my-worklist
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "service_delivery_point_id": 0,
  "service_delivery_point_name": "string",
  "waiting": "string",
  "serving": "string",
  "served_today": 0,
  "cancelled_today": 0
}
```
---

### GET /queue/service-points/{service_delivery_point_id}/worklist
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "service_delivery_point_id": 0,
  "service_delivery_point_name": "string",
  "waiting": "string",
  "serving": "string",
  "served_today": 0,
  "cancelled_today": 0
}
```
---

### GET /queue/service-points/{service_delivery_point_id}/tickets
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /queue/visits/{visit_id}/tickets
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /queue/tickets/{ticket_id}
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/call
**Request Payload (JSON):**
```json
{
  "note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/serve
**Request Payload (JSON):**
```json
{
  "note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/complete
**Request Payload (JSON):**
```json
{
  "note": "string"
}
```
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/complete-and-route
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/complete-and-end-visit
**Request Payload (JSON):**
```json
"string"
```
---

### POST /queue/tickets/{ticket_id}/miss
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/cancel
**Request Payload (JSON):**
```json
{
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

### POST /queue/tickets/{ticket_id}/transfer
**Request Payload (JSON):**
```json
{
  "target_service_delivery_point_id": 0,
  "reason": "string"
}
```
**Response Body (JSON):**
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
---

## 📦 Module: RADIOLOGY
## 📦 Module: REFERRAL
### GET /referrals/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0
}
```
---

### GET /referrals/{referral_id}
**Response Body (JSON):**
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
---

### POST /referrals/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PATCH /referrals/{referral_id}
**Request Payload (JSON):**
```json
{
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "status": "string",
  "priority": "string"
}
```
**Response Body (JSON):**
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
---

### POST /referrals/{referral_id}/cancel
**Response Body (JSON):**
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
---

### POST /referrals/inter-facility
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /referrals/inter-facility/incoming
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0
}
```
---

### POST /referrals/inter-facility/{referral_id}/respond
**Request Payload (JSON):**
```json
{
  "status": "string",
  "note": "string",
  "access_expiry_days": 0
}
```
**Response Body (JSON):**
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
---

## 📦 Module: REIMBURSEMENT
### POST /reimbursements
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### GET /reimbursements
**Response Body (JSON):**
```json
"string"
```
---

### GET /reimbursements/{request_id}
**Response Body (JSON):**
```json
"string"
```
---

### PUT /reimbursements/{request_id}
**Request Payload (JSON):**
```json
{
  "expense_date": "2026-05-09T00:00:00Z",
  "amount": 0.0,
  "category": "string",
  "description": "string",
  "receipt_url": "string"
}
```
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /reimbursements/{request_id}
---

### POST /reimbursements/{request_id}/submit
**Request Payload (JSON):**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: REPORT
### GET /reports/financial-summary
**Response Body (JSON):**
```json
{
  "total_revenue": 0.0,
  "total_invoiced": 0.0,
  "total_paid": 0.0,
  "currency": "string"
}
```
---

### GET /reports/operational-summary
**Response Body (JSON):**
```json
{
  "total_patients": 0,
  "total_active_visits": 0,
  "total_admissions": 0,
  "total_staff": 0
}
```
---

### GET /reports/platform-overview
**Response Body (JSON):**
```json
{
  "total_tenants": 0,
  "active_tenants": 0,
  "total_revenue_platform": 0.0,
  "total_api_calls": 0,
  "system_health_status": "string"
}
```
---

## 📦 Module: ROLE
### GET /roles/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /roles/{role_id}
**Response Body (JSON):**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": "string"
}
```
---

### POST /roles/
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "permission_ids": 0
}
```
**Response Body (JSON):**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": "string"
}
```
---

### PUT /roles/{role_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body (JSON):**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": "string"
}
```
---

### DELETE /roles/{role_id}
---

### POST /roles/{role_id}/permissions
**Request Payload (JSON):**
```json
{
  "permission_ids": 0
}
```
**Response Body (JSON):**
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
    "permissions": "string"
  }
}
```
---

### DELETE /roles/{role_id}/permissions
**Request Payload (JSON):**
```json
{
  "permission_ids": 0
}
```
**Response Body (JSON):**
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
    "permissions": "string"
  }
}
```
---

## 📦 Module: SAAS_ADMIN_PORTAL
### GET /saas/admin/health
**Response Body (JSON):**
```json
"string"
```
---

### POST /saas/admin/migrations/sync
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: SAAS_ADMIN
### GET /saas/admins
**Response Body (JSON):**
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
---

### POST /saas/admins
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /saas/admins/{admin_id}/status
**Request Payload (JSON):**
```json
{
  "status": "string"
}
```
**Response Body (JSON):**
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
---

### GET /saas/admins/{admin_id}
**Response Body (JSON):**
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
---

### PUT /saas/admins/{admin_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /saas/admins/{admin_id}
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: SAAS_DASHBOARD
### GET /saas/dashboard/metrics
**Response Body (JSON):**
```json
"string"
```
---

### GET /saas/dashboard/overview
---

### GET /saas/dashboard/tenants
---

### GET /saas/dashboard/onboarding-pipeline
---

### GET /saas/dashboard/subscriptions
---

### GET /saas/dashboard/billing
---

### GET /saas/dashboard/billing/ageing
---

### GET /saas/dashboard/edge-nodes
---

### GET /saas/dashboard/support-access
---

### GET /saas/dashboard/usage
---

### GET /saas/dashboard/top-tenants
---

### GET /saas/dashboard/recent-activity
---

## 📦 Module: SAAS_NOTIFICATION
### GET /saas/notifications
**Response Body (JSON):**
```json
"string"
```
---

### PATCH /saas/notifications/{notification_id}/read
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: SAAS_SUBSCRIPTION_PLAN
### GET /saas/plans
**Response Body (JSON):**
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
---

### POST /saas/plans
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PUT /saas/plans/{plan_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

## 📦 Module: SAAS_USAGE
### GET /saas/usage/{tenant_id}
**Response Body (JSON):**
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
---

### POST /saas/usage/{tenant_id}/sync
**Response Body (JSON):**
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
---

## 📦 Module: SALARY_ADVANCE
### POST /salary-advances
**Request Payload (JSON):**
```json
{
  "amount": 0.0,
  "reason": "string",
  "repayment_month": "2026-05-09T00:00:00Z",
  "staff_profile_id": 0
}
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /salary-advances
**Response Body (JSON):**
```json
"string"
```
---

### GET /salary-advances/{request_id}
**Response Body (JSON):**
```json
"string"
```
---

### PATCH /salary-advances/{request_id}
**Request Payload (JSON):**
```json
{
  "amount": 0.0,
  "reason": "string",
  "repayment_month": "2026-05-09T00:00:00Z"
}
```
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /salary-advances/{request_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /salary-advances/{request_id}/submit
**Request Payload (JSON):**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: SERVICE_DELIVERY_POINT
### POST /service-delivery-points/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /service-delivery-points/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

### GET /service-delivery-points/active
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

### GET /service-delivery-points/by-code/{code}
**Response Body (JSON):**
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
---

### GET /service-delivery-points/{service_delivery_point_id}
**Response Body (JSON):**
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
---

### PUT /service-delivery-points/{service_delivery_point_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### PATCH /service-delivery-points/{service_delivery_point_id}/status
**Request Payload (JSON):**
```json
{
  "is_active": false
}
```
**Response Body (JSON):**
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
---

### DELETE /service-delivery-points/{service_delivery_point_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

## 📦 Module: SHIFT
### POST /shifts/definitions
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### GET /shifts/definitions
**Response Body (JSON):**
```json
"string"
```
---

### GET /shifts/definitions/{definition_id}
**Response Body (JSON):**
```json
"string"
```
---

### PATCH /shifts/definitions/{definition_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /shifts/definitions/{definition_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /shifts/assignments
**Request Payload (JSON):**
```json
{
  "staff_profile_id": 0,
  "shift_definition_id": 0,
  "shift_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /shifts/assignments
**Response Body (JSON):**
```json
"string"
```
---

### GET /shifts/assignments/{assignment_id}
**Response Body (JSON):**
```json
"string"
```
---

### PATCH /shifts/assignments/{assignment_id}
**Request Payload (JSON):**
```json
{
  "shift_definition_id": 0,
  "shift_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /shifts/assignments/{assignment_id}/check-in
**Response Body (JSON):**
```json
"string"
```
---

### POST /shifts/assignments/{assignment_id}/check-out
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /shifts/assignments/{assignment_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /shifts/swaps
**Request Payload (JSON):**
```json
{
  "requester_assignment_id": 0,
  "target_staff_id": 0,
  "target_assignment_id": 0,
  "reason": "string"
}
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /shifts/swaps/{swap_id}/approve
**Response Body (JSON):**
```json
"string"
```
---

### POST /shifts/swaps/{swap_id}/reject
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: STAFF_PROFILE
### GET /staff-profiles/users
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /staff-profiles/users/{user_id}
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
  "roles": "string",
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
---

### PUT /staff-profiles/users/{user_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users/{user_id}/activate
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users/{user_id}/deactivate
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users/{user_id}/roles/assign
**Request Payload (JSON):**
```json
{
  "role_ids": 0
}
```
**Response Body (JSON):**
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
  "roles": "string",
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
---

### PUT /staff-profiles/users/{user_id}/roles
**Request Payload (JSON):**
```json
{
  "role_ids": 0
}
```
**Response Body (JSON):**
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
  "roles": "string",
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
---

### DELETE /staff-profiles/users/{user_id}/roles
**Request Payload (JSON):**
```json
{
  "role_ids": 0
}
```
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users/{user_id}/password/reset
**Request Payload (JSON):**
```json
{
  "new_password": "string",
  "force_password_change_on_next_login": false
}
```
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users/me/password/change
**Request Payload (JSON):**
```json
{
  "current_password": "string",
  "new_password": "string"
}
```
**Response Body (JSON):**
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
  "roles": "string",
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
---

### POST /staff-profiles/users/{user_id}/mfa
**Request Payload (JSON):**
```json
{
  "enabled": false
}
```
**Response Body (JSON):**
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
  "roles": "string",
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
---

### GET /staff-profiles/users/{user_id}/sessions
**Response Body (JSON):**
```json
"string"
```
---

### POST /staff-profiles/users/{user_id}/sessions/revoke
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /staff-profiles/users/me/sessions/revoke-others
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### GET /staff-profiles/users/{user_id}/access-summary
**Response Body (JSON):**
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
    "roles": "string",
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
  "permissions": "string"
}
```
---

### GET /staff-profiles/
**Response Body (JSON):**
```json
"string"
```
---

### GET /staff-profiles/{staff_profile_id}
**Response Body (JSON):**
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
  "roles": "string"
}
```
---

### GET /staff-profiles/by-user/{user_id}
**Response Body (JSON):**
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
  "roles": "string"
}
```
---

### DELETE /staff-profiles/{staff_profile_id}
**Response Body (JSON):**
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
---

## 📦 Module: STAFF
### POST /staff/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
  "roles": "string",
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
---

### GET /staff/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /staff/{user_id}
**Response Body (JSON):**
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
  "roles": "string"
}
```
---

### PATCH /staff/{user_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
  "roles": "string",
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
---

### DELETE /staff/{staff_profile_id}
---

## 📦 Module: STOCK_MOVEMENT
### GET /stock-movements/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /stock-movements/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /stock-movements/transfer
**Request Payload (JSON):**
```json
{
  "from_stock_item_id": 0,
  "to_store_id": 0,
  "quantity": 0.0,
  "note": "string",
  "performed_by_staff_id": 0
}
```
---

### GET /stock-movements/{movement_id}
**Response Body (JSON):**
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
---

## 📦 Module: SUBSCRIPTION_BILLING
### GET /subscription-billing/invoices
**Response Body (JSON):**
```json
"string"
```
---

### POST /subscription-billing/invoices/issue
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
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
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### POST /subscription-billing/invoices/run-due
---

### POST /subscription-billing/invoices/{invoice_id}/payments
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
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
---

### POST /subscription-billing/invoices/sweep-overdue
---

### GET /subscription-billing/invoices/me
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: SUPPORT_ACCESS
### POST /support-access/request
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /support-access/me
**Response Body (JSON):**
```json
"string"
```
---

### GET /support-access
**Response Body (JSON):**
```json
"string"
```
---

### POST /support-access/{grant_id}/approve
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /support-access/{grant_id}/revoke
**Response Body (JSON):**
```json
"string"
```
---

### POST /support-access/sweep
---

## 📦 Module: SURGICAL
## 📦 Module: TAX
### GET /tax/types
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/types
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### PUT /tax/types/{tax_type_id}
**Request Payload (JSON):**
```json
"2026-05-09T00:00:00Z"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/rates
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/rates
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/rules
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/rules
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/exemptions
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/exemptions
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/invoices/{invoice_id}/compute
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/invoices/{invoice_id}/lines
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/withholding
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/withholding
**Response Body (JSON):**
```json
"string"
```
---

### POST /tax/withholding/{record_id}/remit
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/audit-log
**Response Body (JSON):**
```json
"string"
```
---

### GET /tax/reports/summary
---

## 📦 Module: TEMPLATE
### GET /templates/notifications
**Response Body (JSON):**
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
---

### POST /templates/notifications
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body (JSON):**
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
---

### GET /templates/documents
**Response Body (JSON):**
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
---

### POST /templates/documents
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "template_type": "string",
  "body_html": "string",
  "is_default": false
}
```
**Response Body (JSON):**
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
---

## 📦 Module: TENANT_DASHBOARD
### GET /dashboard/overview
---

### GET /dashboard/today
---

### GET /dashboard/patients
---

### GET /dashboard/visits
---

### GET /dashboard/appointments
---

### GET /dashboard/inpatient
---

### GET /dashboard/billing
---

### GET /dashboard/lab-pharmacy-backlog
---

### GET /dashboard/inventory-alerts
---

### GET /dashboard/hr
---

### GET /dashboard/medication-adherence
---

### GET /dashboard/recent-activity
---

## 📦 Module: TENANT_DOMAIN
### GET /tenant-domains/{tenant_id}
**Response Body (JSON):**
```json
"string"
```
---

### POST /tenant-domains/{tenant_id}
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### GET /tenant-domains/{tenant_id}/{domain_id}/verification
---

### POST /tenant-domains/{tenant_id}/{domain_id}/verify
**Response Body (JSON):**
```json
"string"
```
---

### POST /tenant-domains/{tenant_id}/{domain_id}/make-primary
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /tenant-domains/{tenant_id}/{domain_id}
---

### PUT /tenant-domains/{tenant_id}/{domain_id}/ssl
**Request Payload (JSON):**
```json
"2026-05-09T00:00:00Z"
```
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: TENANT_EMAIL
### GET /tenant-email-config
**Response Body (JSON):**
```json
"string"
```
---

### POST /tenant-email-config
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### PUT /tenant-email-config/{config_id}
**Request Payload (JSON):**
```json
"2026-05-09T00:00:00Z"
```
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /tenant-email-config/{config_id}
---

### POST /tenant-email-config/{config_id}/test
---

### POST /tenant-email-config/{config_id}/send-test
**Request Payload (JSON):**
```json
"string"
```
---

## 📦 Module: TENANT_JOB
### GET /tenant-jobs/handlers
---

### GET /tenant-jobs
**Response Body (JSON):**
```json
"string"
```
---

### POST /tenant-jobs
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### PUT /tenant-jobs/{job_id}
**Request Payload (JSON):**
```json
"2026-05-09T00:00:00Z"
```
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /tenant-jobs/{job_id}
---

## 📦 Module: TENANT_MODULE
### GET /tenant-modules/catalog
---

### GET /tenant-modules/{tenant_id}
**Response Body (JSON):**
```json
"string"
```
---

### PUT /tenant-modules/{tenant_id}
**Request Payload (JSON):**
```json
"string"
```
---

### PUT /tenant-modules/{tenant_id}/bulk
**Request Payload (JSON):**
```json
"string"
```
---

### DELETE /tenant-modules/{tenant_id}/{module_code}
---

### GET /tenant-modules/me/list
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: TENANT_PAYMENT_METHOD
### GET /tenant-payment-methods
**Response Body (JSON):**
```json
"string"
```
---

### POST /tenant-payment-methods
**Request Payload (JSON):**
```json
"string"
```
**Response Body (JSON):**
```json
"string"
```
---

### PUT /tenant-payment-methods/{config_id}
**Request Payload (JSON):**
```json
"2026-05-09T00:00:00Z"
```
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /tenant-payment-methods/{config_id}
---

### POST /tenant-payment-methods/{config_id}/test
---

## 📦 Module: TENANT
### POST /tenants/register
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### POST /tenants/{tenant_id}/approve
**Response Body (JSON):**
```json
"string"
```
---

### GET /tenants
**Response Body (JSON):**
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
        "..."
      ]
    }
  ]
}
```
---

### GET /tenants/{tenant_id}
**Response Body (JSON):**
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
        "id": "...",
        "name": "...",
        "code": "...",
        "description": "...",
        "price": "...",
        "currency": "...",
        "interval": "...",
        "max_facilities": "...",
        "max_users": "...",
        "max_patients": "...",
        "has_clinical": "...",
        "has_inpatient": "...",
        "has_laboratory": "...",
        "has_pharmacy": "...",
        "has_inventory": "...",
        "has_billing": "...",
        "has_reporting": "...",
        "is_active": "..."
      }
    }
  ]
}
```
---

### PUT /tenants/{tenant_id}/status
**Request Payload (JSON):**
```json
{
  "status": "string"
}
```
**Response Body (JSON):**
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
        "id": "...",
        "name": "...",
        "code": "...",
        "description": "...",
        "price": "...",
        "currency": "...",
        "interval": "...",
        "max_facilities": "...",
        "max_users": "...",
        "max_patients": "...",
        "has_clinical": "...",
        "has_inpatient": "...",
        "has_laboratory": "...",
        "has_pharmacy": "...",
        "has_inventory": "...",
        "has_billing": "...",
        "has_reporting": "...",
        "is_active": "..."
      }
    }
  ]
}
```
---

## 📦 Module: TENANT_SETTINGS
### GET /settings
**Response Body (JSON):**
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
---

### PUT /settings
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### POST /settings/logo
**Response Body (JSON):**
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
---

## 📦 Module: TIMESHEET
### POST /timesheets
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### GET /timesheets
**Response Body (JSON):**
```json
"string"
```
---

### GET /timesheets/{timesheet_id}
**Response Body (JSON):**
```json
"string"
```
---

### PUT /timesheets/{timesheet_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /timesheets/{timesheet_id}
---

### POST /timesheets/{timesheet_id}/submit
**Request Payload (JSON):**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: TRIAGE
### GET /triage/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /triage/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /triage/{triage_id}
**Response Body (JSON):**
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
---

### PUT /triage/{triage_id}
**Request Payload (JSON):**
```json
{
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "update_visit_priority": false
}
```
**Response Body (JSON):**
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
---

## 📦 Module: TWO_FACTOR
### GET /two-factor/challenges
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /two-factor/challenges/{challenge_id}
**Response Body (JSON):**
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
---

### POST /two-factor/challenges/{challenge_id}/expire
**Response Body (JSON):**
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
---

### POST /two-factor/users/{user_id}/expire-open-challenges
---

### POST /two-factor/users/{user_id}/policy
**Request Payload (JSON):**
```json
{
  "enable_two_factor": false,
  "reason": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "user_id": 0,
  "is_two_factor_enabled": false
}
```
---

## 📦 Module: USER_PROFILE
### GET /users/me
**Response Body (JSON):**
```json
"string"
```
---

### PUT /users/me
**Request Payload (JSON):**
```json
"2026-05-09T00:00:00Z"
```
**Response Body (JSON):**
```json
"string"
```
---

### POST /users/me/photo
**Response Body (JSON):**
```json
"string"
```
---

### DELETE /users/me/photo
**Response Body (JSON):**
```json
"string"
```
---

## 📦 Module: USER
### GET /users
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### POST /users
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/invite
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "roles": "string",
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
---

### GET /users/{user_id}
**Response Body (JSON):**
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
  "roles": "string",
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
---

### PUT /users/{user_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "roles": "string",
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
---

### PUT /users/{user_id}/status
**Request Payload (JSON):**
```json
{
  "status": "string",
  "reason": "string"
}
```
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/{user_id}/unlock
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/{user_id}/lock
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/{user_id}/deactivate
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/{user_id}/reactivate
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/{user_id}/roles
**Request Payload (JSON):**
```json
{
  "role_ids": 0
}
```
**Response Body (JSON):**
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
    "roles": "string",
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
---

### DELETE /users/{user_id}/roles
**Request Payload (JSON):**
```json
{
  "role_ids": 0
}
```
**Response Body (JSON):**
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
    "roles": "string",
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
---

### POST /users/{user_id}/password-reset
**Request Payload (JSON):**
```json
{
  "new_password": "string",
  "require_change_on_next_login": false,
  "revoke_active_sessions": false
}
```
**Response Body (JSON):**
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
    "roles": "string",
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
---

### GET /users/{user_id}/sessions
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "sessions": "string"
}
```
---

### POST /users/{user_id}/revoke-sessions
**Response Body (JSON):**
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
    "roles": "string",
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
---

### DELETE /users/{user_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "user_id": 0
}
```
---

## 📦 Module: VISIT_FLOW
### POST /visit-flows/templates
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body (JSON):**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### GET /visit-flows/templates
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /visit-flows/templates/{template_id}
**Response Body (JSON):**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### PUT /visit-flows/templates/{template_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body (JSON):**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

### DELETE /visit-flows/templates/{template_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /visit-flows/template-steps
**Request Payload (JSON):**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "template_id": 0
}
```
**Response Body (JSON):**
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
---

### PUT /visit-flows/template-steps/{template_step_id}
**Request Payload (JSON):**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /visit-flows/template-steps/{template_step_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /visit-flows/visit-steps
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /visit-flows/visit-steps
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /visit-flows/visit-steps/{visit_step_id}
**Response Body (JSON):**
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
---

### PUT /visit-flows/visit-steps/{visit_step_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### DELETE /visit-flows/visit-steps/{visit_step_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

### POST /visit-flows/combined-create
**Request Payload (JSON):**
```json
{
  "template": {
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "template_steps": "string",
  "visit_id": 0,
  "visit_steps": "string"
}
```
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "created_template_steps": "string",
  "created_visit_steps": "string"
}
```
---

## 📦 Module: VISIT
### POST /visits/initiate
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "flow_steps": "string",
    "queue_tickets": "string"
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
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "inherited_from_appointment": false,
  "fast_tracked": false
}
```
---

### POST /visits/{visit_id}/reroute
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
    "flow_steps": "string",
    "queue_tickets": "string"
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
---

### GET /visits/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /visits/{visit_id}
**Response Body (JSON):**
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
---

### GET /visits/{visit_id}/detailed
**Response Body (JSON):**
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
  "flow_steps": "string",
  "queue_tickets": "string"
}
```
---

### PUT /visits/{visit_id}
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
  "flow_steps": "string",
  "queue_tickets": "string"
}
```
---

### DELETE /visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

## 📦 Module: VITAL_SIGN
### GET /vital-signs/visits/{visit_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /vital-signs/visits/{visit_id}/latest
**Response Body (JSON):**
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
---

### POST /vital-signs/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

## 📦 Module: WARD
### POST /wards/
**Request Payload (JSON):**
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
**Response Body (JSON):**
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
---

### GET /wards/
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

### GET /wards/{ward_id}
**Response Body (JSON):**
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
---

### GET /wards/{ward_id}/summary
**Response Body (JSON):**
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
---

### PUT /wards/{ward_id}
**Request Payload (JSON):**
```json
{
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string"
}
```
**Response Body (JSON):**
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
---

### DELETE /wards/{ward_id}
**Response Body (JSON):**
```json
{
  "success": false,
  "message": "string"
}
```
---

