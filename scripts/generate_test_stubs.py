import os
import glob
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
TESTS_DIR = APP_DIR / "tests"
UNIT_TESTS_DIR = TESTS_DIR / "unit"
INTEGRATION_TESTS_DIR = TESTS_DIR / "integration"

UNIT_BOILERPLATE = """import pytest
from unittest.mock import MagicMock

@pytest.mark.skip(reason="TODO: Implement unit tests for {module_name}")
class Test{class_name}:
    def test_placeholder(self, db_session):
        # TODO: Setup mock dependencies and execute service methods
        pass
"""

INTEGRATION_BOILERPLATE = """import pytest

@pytest.mark.skip(reason="TODO: Implement integration tests for {module_name}")
class Test{class_name}:
    def test_placeholder(self, client, db_session, admin_user):
        # TODO: Setup database state and make requests to client
        pass
"""

def to_camel_case(snake_str):
    components = snake_str.split('_')
    return "".join(x.title() for x in components)

def generate_unit_tests():
    services_path = APP_DIR / "services" / "*.py"
    for file_path in glob.glob(str(services_path)):
        basename = os.path.basename(file_path)
        if basename == "__init__.py":
            continue
            
        module_name = basename[:-3]  # Remove .py
        test_file_name = f"test_{module_name}.py"
        test_file_path = UNIT_TESTS_DIR / test_file_name
        
        # Check if any test file matching the prefix exists to prevent duplicates
        # e.g., if test_auth.py exists for auth_service.py
        base_prefix = module_name.replace("_service", "")
        alt_test_file_path = UNIT_TESTS_DIR / f"test_{base_prefix}.py"
        
        if test_file_path.exists() or alt_test_file_path.exists():
            print(f"Skipping existing unit test for {module_name}")
            continue
            
        class_name = to_camel_case(module_name)
        content = UNIT_BOILERPLATE.format(module_name=module_name, class_name=class_name)
        
        with open(test_file_path, "w") as f:
            f.write(content)
        print(f"Created unit test stub: {test_file_path}")

def generate_integration_tests():
    routes_path = APP_DIR / "api" / "v1" / "endpoints" / "*.py"
    for file_path in glob.glob(str(routes_path)):
        basename = os.path.basename(file_path)
        if basename == "__init__.py":
            continue
            
        module_name = basename[:-3]  # Remove .py
        test_file_name = f"test_{module_name}.py"
        test_file_path = INTEGRATION_TESTS_DIR / test_file_name
        
        if test_file_path.exists():
            print(f"Skipping existing integration test for {module_name}")
            continue
            
        class_name = to_camel_case(module_name)
        content = INTEGRATION_BOILERPLATE.format(module_name=module_name, class_name=class_name)
        
        with open(test_file_path, "w") as f:
            f.write(content)
        print(f"Created integration test stub: {test_file_path}")

if __name__ == "__main__":
    UNIT_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    INTEGRATION_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Generating Unit Tests...")
    generate_unit_tests()
    
    print("\nGenerating Integration Tests...")
    generate_integration_tests()
    
    print("\nDone.")
