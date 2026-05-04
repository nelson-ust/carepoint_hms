import requests

# 1. Login to get token
r_login = requests.post("http://127.0.0.1:8005/api/v1/auth/login", json={"identifier": "superadmin@carepointhms.com", "password": "SuperAdmin123!"})
token = r_login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Create Admin
r_create = requests.post("http://127.0.0.1:8005/api/v1/saas/admins", json={
    "first_name": "Test",
    "last_name": "Admin",
    "email": "testadmin@carepointhms.com",
    "password": "TestPassword123!",
    "is_superuser": False
}, headers=headers)
print("Create:", r_create.status_code)
admin_id = r_create.json()["id"]

# 3. Get Admin
r_get = requests.get(f"http://127.0.0.1:8005/api/v1/saas/admins/{admin_id}", headers=headers)
print("Get:", r_get.status_code)

# 4. Update Admin
r_update = requests.put(f"http://127.0.0.1:8005/api/v1/saas/admins/{admin_id}", json={
    "first_name": "Updated Test"
}, headers=headers)
print("Update:", r_update.status_code)

# 5. Delete Admin
r_delete = requests.delete(f"http://127.0.0.1:8005/api/v1/saas/admins/{admin_id}", headers=headers)
print("Delete:", r_delete.status_code)
