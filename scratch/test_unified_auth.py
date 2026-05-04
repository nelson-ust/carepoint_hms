import requests

r_login = requests.post("http://127.0.0.1:8005/api/v1/auth/login", json={"identifier": "superadmin@carepointhms.com", "password": "SuperAdmin123!"})
print("Login:", r_login.status_code, r_login.text)

if r_login.status_code == 200:
    token = r_login.json()["access_token"]
    r_me = requests.get("http://127.0.0.1:8005/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    print("Me:", r_me.status_code, r_me.text)
