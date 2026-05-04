import requests

# 1. Login as SaaS Admin
payload = {
    "identifier": "superadmin@carepointhms.com",
    "password": "SuperAdmin123!"
}
res = requests.post("http://0.0.0.0:8005/api/v1/auth/login", json=payload)
if res.status_code != 200:
    print("SaaS Login Failed:", res.text)
    exit(1)

saas_token = res.json()["access_token"]

# 2. Impersonate stnicholas
headers = {
    "Authorization": f"Bearer {saas_token}"
}
impersonate_payload = {
    "tenant_code": "stnicholas"
}
res = requests.post("http://0.0.0.0:8005/api/v1/auth/impersonate", json=impersonate_payload, headers=headers)
if res.status_code != 200:
    print("Impersonate Failed:", res.text)
    exit(1)

tenant_token = res.json()["access_token"]
print("Successfully got impersonated token!")

# 3. Trigger Backup
tenant_headers = {
    "Authorization": f"Bearer {tenant_token}",
    "x-tenant": "stnicholas"
}
res = requests.post("http://0.0.0.0:8005/api/v1/backups", headers=tenant_headers)
print("Backup POST Response:", res.status_code)
if res.status_code != 200:
    print(res.text)
else:
    print("Backup Data:", res.json())

# 4. List Backups
res = requests.get("http://0.0.0.0:8005/api/v1/backups", headers=tenant_headers)
print("Backups GET Response:", res.status_code)
if res.status_code != 200:
    print(res.text)
else:
    print("Backups List:", res.json())
