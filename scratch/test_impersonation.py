import requests

# 1. Login as SaaS Admin
payload = {
    "identifier": "superadmin@carepointhms.com",
    "password": "SuperAdmin123!"
}
res = requests.post("http://0.0.0.0:8005/api/v1/auth/login", json=payload)
print("SaaS Login Response:", res.status_code)
if res.status_code != 200:
    print(res.text)
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
print("Impersonate Response:", res.status_code)
if res.status_code != 200:
    print(res.text)
    exit(1)

tenant_token = res.json()["access_token"]
print("Successfully got impersonated token!")

# 3. Hit Tenant Settings Endpoint
tenant_headers = {
    "Authorization": f"Bearer {tenant_token}",
    "x-tenant": "stnicholas"
}
res = requests.get("http://0.0.0.0:8005/api/v1/settings", headers=tenant_headers)
print("Settings GET Response:", res.status_code)
if res.status_code != 200:
    print(res.text)
else:
    print("Settings Data:", res.json())

# 4. Update Settings Endpoint
update_payload = {
    "theme_config": {"primary_color": "#ff0000"}
}
res = requests.put("http://0.0.0.0:8005/api/v1/settings", json=update_payload, headers=tenant_headers)
print("Settings PUT Response:", res.status_code)
if res.status_code != 200:
    print(res.text)
else:
    print("Settings Updated Data:", res.json())
