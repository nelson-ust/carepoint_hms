import requests

headers = {
    "x-tenant": "stnicholas"
}

# 1. Login as standard user (tenant admin)
r_login = requests.post(
    "http://127.0.0.1:8005/api/v1/auth/login", 
    json={"identifier": "admin", "password": "Password123!"},
    headers=headers
)
print(r_login.status_code, r_login.text)
if "access_token" in r_login.json():
    token = r_login.json()["access_token"]
    headers["Authorization"] = f"Bearer {token}"

    # 2. Try creating users to hit the limit
    for i in range(15):
        r_create = requests.post("http://127.0.0.1:8005/api/v1/users", json={
            "first_name": f"Test{i}",
            "last_name": "User",
            "email": f"testuser{i}@carepointhms.com",
            "password": "Password123!",
            "username": f"testuser{i}",
            "phone_number": f"+23480000000{i:02d}",
            "role_ids": []
        }, headers=headers)
        print(f"User {i}:", r_create.status_code, r_create.text[:200])
        if r_create.status_code == 400 and "User limit reached" in r_create.text:
            print("Successfully hit the user limit!")
            break

