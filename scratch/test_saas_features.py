import requests

# 1. Login to get token
r_login = requests.post("http://127.0.0.1:8005/api/v1/auth/login", json={"identifier": "superadmin@carepointhms.com", "password": "SuperAdmin123!"})
token = r_login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Test Dashboard Metrics
r_metrics = requests.get("http://127.0.0.1:8005/api/v1/saas/dashboard/metrics", headers=headers)
print("Dashboard:", r_metrics.status_code, r_metrics.text[:200])

# 3. Test Tenants List
r_tenants = requests.get("http://127.0.0.1:8005/api/v1/tenants", headers=headers)
print("Tenants:", r_tenants.status_code, r_tenants.text[:200])

# 4. Test Subscription Plans List
r_plans = requests.get("http://127.0.0.1:8005/api/v1/saas/plans", headers=headers)
print("Plans:", r_plans.status_code, r_plans.text[:200])

# 5. Test Admins List
r_admins = requests.get("http://127.0.0.1:8005/api/v1/saas/admins", headers=headers)
print("Admins:", r_admins.status_code, r_admins.text[:200])
