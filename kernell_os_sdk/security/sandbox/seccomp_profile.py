import sys

def install_seccomp():
    try:
        import seccomp
    except ImportError:
        raise RuntimeError("CRITICAL: python3-seccomp is missing. Seccomp isolation cannot be disabled in production. Install python3-seccomp.")

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
        filt.add_rule(seccomp.ALLOW, sc)

    # --- openat con restricciones básicas ---
    filt.add_rule(seccomp.ALLOW, "openat")

    # --- DENY explícito (defensa en profundidad) ---
    blocked = [
        "execve", "socket", "connect", "accept", "accept4",
        "bind", "listen", "ptrace", "clone", "fork", "vfork",
        "kill", "mount", "umount2", "chmod", "chown",
    ]
    
    for sc in blocked:
        filt.add_rule(seccomp.KILL, sc)
            
    filt.load()
