import re

with open('/Users/nelsonattah/Projects/carepoint_hms/app/models/all_models.py', 'r') as f:
    content = f.read()

constraints = re.findall(r'UniqueConstraint\(.*?, name="(\w+)"\)', content)
indexes = re.findall(r'Index\("(\w+)"', content)

names = {}
for name in constraints:
    names.setdefault(name, []).append("UniqueConstraint")
for name in indexes:
    names.setdefault(name, []).append("Index")

for name, types in names.items():
    if len(types) > 1:
        print(f"Collision: {name} in {types}")
