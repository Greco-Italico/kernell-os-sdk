import sys

def install_seccomp():
    try:
        import seccomp
    except ImportError:
        print("Warning: python3-seccomp not installed. Seccomp disabled.", file=sys.stderr)
        return

    # Default: KILL process
    filt = seccomp.SyscallFilter(defaction=seccomp.KILL)
    
    # --- ALLOW LIST (mínimo viable) ---
    allowed_syscalls = [
        "read",
        "write",
        "exit",
        "exit_group",
        "brk",
        "mmap",
        "munmap",
        "close",
        "fstat",
        "rt_sigreturn",
        "rt_sigaction",
        "lseek",
        "getpid",
        "gettid",
        "clock_gettime",
    ]
    
    for sc in allowed_syscalls:
        try:
            filt.add_rule(seccomp.ALLOW, sc)
        except Exception:
            pass

    # --- openat con restricciones básicas ---
    try:
        filt.add_rule(seccomp.ALLOW, "openat")
    except Exception:
        pass

    # --- DENY explícito (defensa en profundidad) ---
    blocked = [
        "execve", "socket", "connect", "accept", "accept4",
        "bind", "listen", "ptrace", "clone", "fork", "vfork",
        "kill", "mount", "umount2", "chmod", "chown",
    ]
    
    for sc in blocked:
        try:
            filt.add_rule(seccomp.KILL, sc)
        except Exception:
            pass
            
    filt.load()
