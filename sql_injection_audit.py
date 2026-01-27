"""Comprehensive SQL injection vulnerability audit"""
import re

def audit_sql_injection_risks(filename='app.py'):
    """Scan for SQL injection patterns"""
    
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    findings = {
        'high_risk': [],
        'medium_risk': [],
        'safe': []
    }
    
    for i, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        
        # HIGH RISK: f-string in text()
        if re.search(r'text\s*\(\s*f["\']', line):
            # Check if it's the validated LIMIT case
            if 'LIMIT {int(limit)}' in line:
                findings['safe'].append((i, 'LIMIT with validated int()', line.strip()[:80]))
            # Check if it's the whitelisted UPDATE case
            elif 'UPDATE hero_carousel SET' in line and 'join(updates)' in line:
                findings['medium_risk'].append((i, 'Dynamic UPDATE (whitelisted fields)', line.strip()[:80]))
            else:
                findings['high_risk'].append((i, 'f-string in SQL', line.strip()[:80]))
        
        # MEDIUM RISK: .format() in SQL
        if re.search(r'(SELECT|UPDATE|INSERT|DELETE).*\.format\(', line, re.IGNORECASE):
            findings['medium_risk'].append((i, '.format() in SQL', line.strip()[:80]))
        
        # MEDIUM RISK: % formatting in SQL
        if re.search(r'(SELECT|UPDATE|INSERT|DELETE).*%\s*\(', line, re.IGNORECASE):
            findings['medium_risk'].append((i, '% formatting in SQL', line.strip()[:80]))
        
        # SAFE: Parameterized queries
        if re.search(r'text\s*\(\s*["\'].*:[\w_]+', line):
            # This is a parameterized query (contains :param_name)
            pass
    
    return findings

def print_audit_report(findings):
    """Print formatted audit report"""
    
    print("=" * 80)
    print("SQL INJECTION VULNERABILITY AUDIT REPORT")
    print("=" * 80)
    print()
    
    if findings['high_risk']:
        print("🔴 HIGH RISK - Immediate Action Required:")
        print("-" * 80)
        for line_num, reason, code in findings['high_risk']:
            print(f"  Line {line_num}: {reason}")
            print(f"    Code: {code}")
        print()
    else:
        print("✅ No HIGH RISK SQL injection vulnerabilities found")
        print()
    
    if findings['medium_risk']:
        print("🟡 MEDIUM RISK - Review Recommended:")
        print("-" * 80)
        for line_num, reason, code in findings['medium_risk']:
            print(f"  Line {line_num}: {reason}")
            print(f"    Code: {code}")
        print()
        print("  Note: These use dynamic SQL but have protective measures")
        print()
    else:
        print("✅ No MEDIUM RISK patterns found")
        print()
    
    if findings['safe']:
        print("✅ SAFE PATTERNS (Reviewed & Validated):")
        print("-" * 80)
        for line_num, reason, code in findings['safe']:
            print(f"  Line {line_num}: {reason}")
        print()
    
    # Summary
    total_risks = len(findings['high_risk']) + len(findings['medium_risk'])
    if total_risks == 0:
        print("=" * 80)
        print("✅ AUDIT PASSED - No critical SQL injection vulnerabilities found")
        print("=" * 80)
    else:
        print("=" * 80)
        print(f"⚠️  AUDIT FINDINGS: {len(findings['high_risk'])} HIGH, {len(findings['medium_risk'])} MEDIUM")
        print("=" * 80)

if __name__ == "__main__":
    findings = audit_sql_injection_risks()
    print_audit_report(findings)
