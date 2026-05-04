import os
import re

def modernize_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Pattern for class Config: ... from_attributes = True
    config_pattern = re.compile(r'\s+class Config:\s+from_attributes = True')
    
    if not config_pattern.search(content):
        return False

    # Add ConfigDict to pydantic imports
    if 'from pydantic import' in content:
        if 'ConfigDict' not in content:
            content = re.sub(r'from pydantic import ([\w, ]+)', r'from pydantic import \1, ConfigDict', content)
    elif 'import pydantic' in content:
        pass # Handle pydantic.ConfigDict later if needed
    else:
        # No pydantic import? Unlikely if there's a Config class, but let's be safe
        content = "from pydantic import ConfigDict\n" + content

    # Replace class Config blocks
    # Handle both spaces and tabs, and optional empty lines
    content = re.sub(r'(\s+)class Config:\s+from_attributes = True', r'\1model_config = ConfigDict(from_attributes=True)', content)

    with open(filepath, 'w') as f:
        f.write(content)
    return True

# Walk through app directory
for root, dirs, files in os.walk('app'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            if modernize_file(path):
                print(f"Modernized: {path}")
