import re

def camel_to_snake(name):
    step_1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step_1).lower()

with open('/Users/nelsonattah/Projects/carepoint_hms/app/models/all_models.py', 'r') as f:
    content = f.read()

classes = re.findall(r'class (\w+)\(BaseTable\):', content)
index_names = {}

for cls in classes:
    table = camel_to_snake(cls)
    # Default index for ID
    idx_id = f"ix_{table}_id"
    index_names.setdefault(idx_id, []).append((cls, "id"))
    
    # Search for other index=True in this class
    class_start = content.find(f"class {cls}(BaseTable):")
    # Find next class or end of file
    next_class_match = re.search(r'\nclass \w+\(BaseTable\):', content[class_start+1:])
    if next_class_match:
        block = content[class_start:class_start + next_class_match.start()]
    else:
        block = content[class_start:]
    
    # Find columns with index=True
    # Match pattern: col_name: Mapped[...] = mapped_column(...index=True...)
    col_matches = re.findall(r'^\s+(\w+): Mapped\[.*?\] = mapped_column\(.*?index=True', block, re.M | re.S)
    for col in col_matches:
        idx_col = f"ix_{table}_{col}"
        index_names.setdefault(idx_col, []).append((cls, col))

for name, locations in index_names.items():
    if len(locations) > 1:
        # Filter out duplicates within the same class/col
        unique_locs = list(set(locations))
        if len(unique_locs) > 1:
            print(f"Collision: {name} at {unique_locs}")
