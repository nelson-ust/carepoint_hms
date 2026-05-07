import os
os.environ["PYTHONPATH"] = "/Users/nelsonattah/Projects/carepoint_hms"
from sqlalchemy.engine import make_url
from app.core.database import MASTER_DATABASE_URL

url = make_url(MASTER_DATABASE_URL)
print(f"Original URL: {MASTER_DATABASE_URL}")
print(f"Password in original URL object: {url.password}")

new_url = url.set(database="postgres")
new_url_str = str(new_url)
print(f"New URL str: {new_url_str}")

new_url_obj = make_url(new_url_str)
print(f"Password in new URL object: {new_url_obj.password}")
