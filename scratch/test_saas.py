import requests, jwt
r_login = requests.post("http://127.0.0.1:8005/api/v1/saas/auth/login", json={"email": "superadmin@carepointhms.com", "password": "SuperAdmin123!"})
token = r_login.json()["access_token"]
print("Payload:", jwt.decode(token, options={"verify_signature": False}))
r_me = requests.get("http://127.0.0.1:8005/api/v1/saas/auth/me", headers={"Authorization": f"Bearer {token}"})
print("Me:", r_me.status_code, r_me.text)
