#!/usr/bin/env python3
"""
Batch-fix PytestReturnNotNoneWarning across all integration test files.
Pattern: extract `return <data>` from test methods into `_create_*` helpers.
"""
import re
import sys
from pathlib import Path

BASE = Path("/Users/nelsonattah/Projects/carepoint_hms/app/tests/integration")

# For each file, define the pattern: (test_method_name, helper_name)
# The script will:
# 1. Extract the body of test_method_name into helper_name (private method)
# 2. Make test_method_name call helper_name without returning
# 3. Update all self.test_method_name() calls to self.helper_name()

def fix_file(filepath: Path):
    content = filepath.read_text()
    
    # Find all test methods that end with `return ...`
    # Pattern: def test_xxx(self, ...): ... return <something>
    lines = content.split('\n')
    modified = False
    
    # Build a map of test methods that return values
    returning_tests = {}  # method_name -> (start_line_idx, end_line_idx)
    
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match: def test_xxx(self, ...):
        m = re.match(r'^(\s+)def (test_\w+)\(self,', line)
        if m:
            indent = m.group(1)
            method_name = m.group(2)
            # Find the end of this method (next def at same indent or end of class)
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Check if next method/class at same or lower indent
                if next_line.strip() and not next_line.startswith(indent + ' ') and not next_line.startswith(indent + '\t'):
                    if next_line.startswith(indent + 'def ') or next_line.startswith('class ') or (next_line.strip() and not next_line[0].isspace()):
                        break
                j += 1
            
            # Check if method ends with return <something>
            end_idx = j
            # Find last non-empty line
            last_line_idx = end_idx - 1
            while last_line_idx > i and not lines[last_line_idx].strip():
                last_line_idx -= 1
            
            if last_line_idx > i and lines[last_line_idx].strip().startswith('return ') and lines[last_line_idx].strip() != 'return None':
                returning_tests[method_name] = (i, end_idx)
            
            i = j
        else:
            i += 1
    
    if not returning_tests:
        return False
    
    # Now process: for each returning test method, create a helper
    new_lines = []
    skip_until = -1
    
    for i, line in enumerate(lines):
        if i < skip_until:
            continue
        
        # Check if this line starts a returning test method
        found_method = None
        for method_name, (start, end) in returning_tests.items():
            if i == start:
                found_method = method_name
                break
        
        if found_method:
            start, end = returning_tests[found_method]
            method_lines = lines[start:end]
            indent = re.match(r'^(\s+)', method_lines[0]).group(1)
            
            # Create helper name: test_create_xxx -> _create_xxx
            helper_name = found_method.replace('test_', '_', 1)
            
            # Create helper method (copy of original with renamed def)
            helper_lines = list(method_lines)
            helper_lines[0] = helper_lines[0].replace(f'def {found_method}(', f'def {helper_name}(', 1)
            
            # Create test method that calls helper without return
            sig_match = re.match(r'^(\s+)def \w+\((.*?)\):', method_lines[0])
            params = sig_match.group(2) if sig_match else 'self'
            
            test_method = [
                f'{indent}def {found_method}({params}):',
                f'{indent}    self.{helper_name}({", ".join(p.strip().split(":")[0].split("=")[0].strip() for p in params.split(","))})',
                ''
            ]
            
            # Add helper first, then test method
            new_lines.extend(helper_lines)
            new_lines.append('')
            new_lines.extend(test_method)
            
            skip_until = end
            modified = True
        else:
            # Replace self.test_xxx() calls with self._xxx()
            new_line = line
            for method_name in returning_tests:
                helper_name = method_name.replace('test_', '_', 1)
                new_line = new_line.replace(f'self.{method_name}(', f'self.{helper_name}(')
            new_lines.append(new_line)
    
    if modified:
        filepath.write_text('\n'.join(new_lines))
        print(f"Fixed: {filepath.name}")
    return modified

# Files to fix
files = [
    "test_appointment_routes.py",
    "test_bed_routes.py",
    "test_billing_routes.py",
    "test_consultation_routes.py",
    "test_department_routes.py",
    "test_diagnosis_routes.py",
    "test_discharge_routes.py",
    "test_drug_routes.py",
    "test_inventory_routes.py",
    "test_invoice_routes.py",
    "test_lab_order_routes.py",
    "test_lab_result_routes.py",
    "test_payment_routes.py",
    "test_prescription_routes.py",
    "test_procedure_routes.py",
    "test_role_routes.py",
    "test_service_delivery_point_routes.py",
    "test_tenant_routes.py",
    "test_triage_routes.py",
    "test_visit_flow_routes.py",
    "test_vital_sign_routes.py",
    "test_ward_routes.py",
]

count = 0
for f in files:
    fp = BASE / f
    if fp.exists() and fix_file(fp):
        count += 1

print(f"\nFixed {count}/{len(files)} files")
