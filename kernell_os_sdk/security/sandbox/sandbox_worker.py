import os
import sys
import json
from kernell_os_sdk.security.sandbox.seccomp_profile import install_seccomp

def close_fds():
    max_fd = 1024
    for fd in range(3, max_fd):
        try:
            os.close(fd)
        except OSError:
            pass

def drop_privileges():
    try:
        os.setgid(65534)
        os.setuid(65534)
    except Exception:
        pass

def main():
    close_fds()
    drop_privileges()
    
    install_seccomp()
    
    raw = sys.stdin.read()
    if not raw:
        sys.exit(1)
        
    payload = json.loads(raw)
    
    from kernell_os_sdk.security.intent_firewall import OrchestratorStub, PlanIR, CapabilityToken
    
    plan = PlanIR(**payload["plan"])
    token = CapabilityToken(**payload["token"])
    
    orchestrator = OrchestratorStub(authority=None)
    result = orchestrator.execute(plan, token)
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
