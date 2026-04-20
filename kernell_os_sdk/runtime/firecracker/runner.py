import socket
import os

VSOCK_PORT = 5000

def safe_exec(code: str):
    SAFE_BUILTINS = {
        "print": print,
        "range": range,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
    }

    try:
        # Wrap the code like we did in SubprocessRuntime to capture output 
        # or just execute it directly.
        # Since standard exec() stdout goes to console, we can capture it
        import io
        import sys
        
        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()
        
        try:
            exec(code, {"__builtins__": SAFE_BUILTINS}, {})
            output = redirected_output.getvalue()
            return output if output else "OK"
        finally:
            sys.stdout = old_stdout
            
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {str(e)}"

def main():
    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.bind((socket.VMADDR_CID_ANY, VSOCK_PORT))
    s.listen(1)

    print("[VM_READY]", flush=True)

    conn, _ = s.accept()
    print("[VM] vsock connected, waiting for payload...", flush=True)

    data = conn.recv(65536).decode()
    
    if len(data) > 10000:
        conn.send("ERROR: payload too large".encode())
    else:
        print("[VM] executing payload...")
        result = safe_exec(data)
        conn.send(result.encode())
        
    conn.close()

if __name__ == "__main__":
    main()
