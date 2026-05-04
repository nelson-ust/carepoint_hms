import requests
import json

BASE_URL = "http://localhost:8005/api/v1"
# Assuming we have a valid token for a tenant admin from previous sessions or a default one
# For verification in this environment, I'll use the superuser/master-admin credentials if possible
# But usually, I should use a tenant-specific token.
# Let's try to get a token first.

def get_token(username, password, tenant_code=None):
    headers = {}
    if tenant_code:
        headers["x-tenant"] = tenant_code
    
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"identifier": username, "password": password},
        headers=headers
    )
    if resp.status_code == 200:
        return resp.json()["tokens"]["access_token"]
    else:
        print(f"Login failed: {resp.text}")
        return None

# Use known test credentials
token = get_token("admin", "Admin123!", "stnicholas")
if not token:
    # Try another one
    token = get_token("saas_admin@carepoint.com", "Admin123!") # No tenant for master login

if token:
    headers = {"Authorization": f"Bearer {token}", "x-tenant": "stnicholas"}
    
    # 1. Test Facilities
    print("\n--- Testing Facilities ---")
    resp = requests.get(f"{BASE_URL}/facilities", headers=headers)
    print(f"List Facilities: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Count: {len(resp.json())}")

    # 2. Test Settings Update
    print("\n--- Testing Settings Update ---")
    payload = {
        "primary_color": "#FF5733",
        "invoice_prefix": "CARE-INV",
        "timezone": "Africa/Lagos"
    }
    resp = requests.put(f"{BASE_URL}/settings", json=payload, headers=headers)
    print(f"Update Settings: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Primary Color: {data.get('primary_color')}")
        print(f"Invoice Prefix: {data.get('invoice_prefix')}")

    # 3. Test User Invite
    print("\n--- Testing User Invite ---")
    invite_payload = {
        "username": "invited_nurse",
        "email": "nurse@example.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "phone_number": "08012345678",
        "role_ids": [] # Just empty for now
    }
    resp = requests.post(f"{BASE_URL}/users/invite", json=invite_payload, headers=headers)
    print(f"Invite User: {resp.status_code}")
    if resp.status_code != 201:
        print(f"Error: {resp.text}")
    # 4. Test Audit Logging (Patient Update)
    print("\n--- Testing Audit Logging ---")
    patient_payload = {
        "first_name": "Audit",
        "last_name": "Test",
        "gender": "MALE",
        "date_of_birth": "1990-01-01",
        "phone_number": "08011112222"
    }
    resp = requests.post(f"{BASE_URL}/patients", json=patient_payload, headers=headers)
    if resp.status_code == 201:
        patient_id = resp.json()["patient_id"]
        print(f"Patient Created: {patient_id}")
        
        # Update patient
        update_payload = {"first_name": "AuditUpdated"}
        resp = requests.put(f"{BASE_URL}/patients/{patient_id}", json=update_payload, headers=headers)
        print(f"Patient Updated: {resp.status_code}")
        
        # Check audit logs (if endpoint exists)
        # For now we just verify it didn't crash
    else:
        print(f"Patient Creation Failed: {resp.text}")
else:
    print("Could not obtain token for verification.")
