import os
from pathlib import Path

def replace_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    new_content = content.replace("SUPER_ADMIN", "TENANT_ADMIN")
    new_content = new_content.replace("Super Admin", "Tenant Admin")
    
    if content != new_content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

def main():
    app_dir = Path("/Users/nelsonattah/Projects/carepoint_hms/app")
    for root, _, files in os.walk(app_dir):
        for file in files:
            if file.endswith('.py'):
                replace_in_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
