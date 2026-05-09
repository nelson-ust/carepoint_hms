# Carepoint HMS — API Technical Documentation

## Overview
This document outlines the technical integration patterns for the Carepoint Health Management System. It describes the sequence of operations required to manage a multi-tenant healthcare environment.

## 1. Multi-Tenant Architecture
Carepoint HMS uses a "Database-per-Tenant" or "Schema-per-Tenant" isolation model.

### 1.1 Tenant Resolution
The system identifies the active tenant via the `X-Tenant-Code` header.
- **Header**: `X-Tenant-Code`
- **Example Value**: `stnicholas`

## 2. Authentication Protocol
Authentication is stateless via JWT (JSON Web Tokens).

### 2.1 Staff/Admin Login
- **Endpoint**: `/api/v1/auth/login`
- **Method**: POST
- **Payload**:
  ```json
  {
    "identifier": "nelson.attah@live.com",
    "password": "S3cure!Password2026",
    "remember_me": false
  }
  ```

## 3. Core Operational Flows

### 3.1 Facility & Infrastructure Setup
1. **Network**: `POST /facilities/networks/create` (e.g., "General Hospital Group")
2. **Facility**: `POST /facilities` (e.g., "St. Nicholas Branch A")
3. **Department**: `POST /departments` (e.g., "Radiology")
4. **Service Point**: `POST /service-delivery-points` (e.g., "Front Desk")

### 3.2 Patient Management Flow
1. **Registration**: `POST /patients`
2. **Visit Initiation**: `POST /visits/initiate`
3. **Queueing**: The visit automatically generates a ticket in the `Queue` system.
4. **Triage**: `POST /triage` or `POST /vital-signs`

### 3.3 Laboratory & Diagnostics
1. **Order**: `POST /lab/orders`
2. **Specimen Collection**: `PATCH /lab/orders/{id}/collect`
3. **Resulting**: `POST /lab/results`

### 3.4 Pharmacy & Inventory
1. **Prescription**: `POST /prescriptions`
2. **Dispensing**: `POST /dispense`
3. **Stock Adjustment**: `POST /inventory/stock-adjustments`

## 4. Financial Operations
- **Invoicing**: `POST /invoices` (Consolidates charges from visits, lab, and pharmacy)
- **Payments**: `POST /payments` (Records transaction against an invoice)

## 5. Patient Self-Service Portal
- **Registration**: `POST /portal/register`
- **Authentication**: OTP-based via `/portal/auth/request-otp` and `/portal/auth/verify-otp`.
- **Dashboard**: `GET /portal/dashboard`

---
*Documentation Generated: 2026-05-08*
