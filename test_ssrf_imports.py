import os
import re
from pathlib import Path

def test_no_raw_httpx_imports():
    """
    Ensures that no module imports httpx directly except the SSRF wrapper.
    All HTTP access must go through kernell_os_sdk.security.ssrf
    """
    sdk_dir = Path(__file__).parent / "kernell_os_sdk"
    
    # Exceptions where httpx import is strictly allowed
    ALLOWED_FILES = {
        "security/ssrf.py",
    }
    
    # We still allow catching httpx exceptions if they import httpx locally or just use Exception, 
    # but the strictest rule is NO import httpx at all. Let's look for standard usage.
    FORBIDDEN_PATTERNS = [
        re.compile(r'^\s*import httpx\s*$'),
        re.compile(r'^\s*from httpx import.*Client.*'),
        re.compile(r'httpx\.get\('),
        re.compile(r'httpx\.post\('),
        re.compile(r'httpx\.Client\('),
        re.compile(r'httpx\.AsyncClient\('),
    ]

    violations = []

    for root, dirs, files in os.walk(sdk_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
                
            filepath = Path(root) / file
            rel_path = filepath.relative_to(sdk_dir).as_posix()
            
            if rel_path in ALLOWED_FILES:
                continue
                
            try:
                content = filepath.read_text(encoding="utf-8")
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    # Local exception blocks might do `import httpx` to catch exceptions
                    # but we flag them anyway to be strict.
                    for pattern in FORBIDDEN_PATTERNS:
                        if pattern.search(line):
                            violations.append(f"{rel_path}:{i+1} -> {line.strip()}")
            except UnicodeDecodeError:
                pass

    if violations:
        print("🚨 SECURITY POLICY VIOLATION 🚨")
        print("Direct httpx usage is forbidden to prevent SSRF. Use kernell_os_sdk.security.ssrf wrappers.")
        for v in violations:
            print(f" - {v}")
        raise AssertionError("Found raw httpx imports/calls outside of security/ssrf.py")
        
    print("✅ SSRF Import Policy Check Passed. No raw httpx usage found.")

if __name__ == "__main__":
    test_no_raw_httpx_imports()
