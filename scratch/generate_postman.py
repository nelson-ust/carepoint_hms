import json
import os
import sys
from fastapi.routing import APIRoute

# Add the current directory to sys.path to import the app
sys.path.append(os.getcwd())

from app.main import app

SAMPLE_DATA = {
    "/api/v1/auth/login": {
        "identifier": "admin",
        "password": "Password123",
        "remember_me": True
    },
    "/api/v1/auth/otp/verify": {
        "otp_code": "123456",
        "challenge_reference": "REF123",
        "purpose": "LOGIN_2FA"
    },
    "/api/v1/auth/two-factor/verify": {
        "otp_code": "123456",
        "method": "EMAIL"
    },
    "/api/v1/patients/": {
        "first_name": "John",
        "last_name": "Doe",
        "middle_name": "Quincy",
        "date_of_birth": "1990-01-01",
        "gender": "MALE",
        "phone_number": "+2348012345678",
        "email": "john.doe@example.com",
        "address": "123 Medical Way",
        "city": "Lagos",
        "state": "Lagos",
        "country": "Nigeria",
        "blood_group": "O_POSITIVE",
        "genotype": "AA"
    },
    "/api/v1/users/": {
        "username": "jdoe",
        "email": "jdoe@example.com",
        "password": "Password123",
        "first_name": "John",
        "last_name": "Doe",
        "role_ids": [1]
    },
    "/api/v1/appointments/": {
        "patient_id": 1,
        "appointment_date": "2026-05-01T10:00:00",
        "appointment_type": "CONSULTATION",
        "notes": "Regular checkup"
    },
    "/api/v1/vitals/": {
        "patient_id": 1,
        "visit_id": 1,
        "temperature": 36.5,
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 80,
        "pulse_rate": 72,
        "respiratory_rate": 16,
        "oxygen_saturation": 98
    }
}

def generate_postman_collection():
    collection = {
        "info": {
            "name": "Carepoint HMS - Sequential API Collection",
            "description": "Sequential Postman collection for Carepoint Hospital Management System API with sample data.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [],
        "variable": [
            {
                "key": "baseUrl",
                "value": "http://localhost:8005",
                "type": "string"
            },
            {
                "key": "accessToken",
                "value": "",
                "type": "string"
            }
        ],
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{accessToken}}",
                    "type": "string"
                }
            ]
        }
    }

    # Group routes by tags
    folders = {}

    for route in app.routes:
        if isinstance(route, APIRoute):
            tag = route.tags[0] if route.tags else "Default"
            if tag not in folders:
                folders[tag] = {
                    "name": tag,
                    "item": []
                }
            
            # Create request item
            path_segments = [s for s in route.path.split("/") if s]
            
            # Prepare request body
            body = None
            if route.methods.intersection({"POST", "PUT", "PATCH"}):
                sample = SAMPLE_DATA.get(route.path)
                if not sample:
                    # Generic placeholder for unknown bodies
                    sample = {"placeholder": "Check documentation for schema"}
                
                body = {
                    "mode": "raw",
                    "raw": json.dumps(sample, indent=2),
                    "options": {
                        "raw": {
                            "language": "json"
                        }
                    }
                }

            item = {
                "name": route.summary or route.name or route.path,
                "request": {
                    "method": list(route.methods)[0],
                    "header": [],
                    "url": {
                        "raw": "{{baseUrl}}" + route.path,
                        "host": ["{{baseUrl}}"],
                        "path": path_segments
                    }
                },
                "event": []
            }

            if body:
                item["request"]["body"] = body
            
            # Add a test script to capture the token if it's a login response
            if "/auth/login" in route.path:
                item["event"].append({
                    "listen": "test",
                    "script": {
                        "exec": [
                            "var jsonData = pm.response.json();",
                            "if (jsonData.tokens && jsonData.tokens.access_token) {",
                            "    pm.collectionVariables.set(\"accessToken\", jsonData.tokens.access_token);",
                            "}"
                        ],
                        "type": "text/javascript"
                    }
                })

            folders[tag]["item"].append(item)

    # Sort tags in a logical order
    tag_order = [
        "Auth", "TwoFactor", "Roles", "Permissions", "Users",
        "Service Delivery Points", "Wards", "Beds",
        "Patients", "Patient Registration", "Visits", "Visit Flow", "Queues",
        "Triage", "Vital Signs", "Consultations", "Diagnosis",
        "Laboratory", "Lab Orders", "Lab Results",
        "Drugs", "Inventory", "Stock Movements", "Prescriptions", "Dispense", "Pharmacy",
        "Admissions", "Discharge",
        "Billing", "Invoices", "Payments",
        "Appointments", "Ambulance", "Notifications", "Compliance",
        "Procedures", "Radiology", "Surgical", "Insurance",
        "Health", "Root"
    ]

    # Map actual tags to our order
    sorted_folders = []
    found_tags = set(folders.keys())
    
    for ordered_tag in tag_order:
        match = next((t for t in found_tags if ordered_tag.lower() in t.lower()), None)
        if match:
            sorted_folders.append(folders[match])
            found_tags.remove(match)
    
    # Add remaining tags
    for tag in sorted(found_tags):
        sorted_folders.append(folders[tag])

    collection["item"] = sorted_folders

    with open("carepoint_hms_sequential_collection.json", "w") as f:
        json.dump(collection, f, indent=2)
    
    print("Sequential Postman collection generated with sample data: carepoint_hms_sequential_collection.json")

if __name__ == "__main__":
    generate_postman_collection()
