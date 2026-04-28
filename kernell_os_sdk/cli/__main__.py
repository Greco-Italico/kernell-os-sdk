import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: kernell [init|doctor|demo|cloud|dashboard]")
        return

    cmd = sys.argv[1]

    if cmd == "init":
        from kernell_os_sdk.cli.init import main as run
    elif cmd == "doctor":
        from kernell_os_sdk.cli.doctor import main as run
    elif cmd == "demo":
        from kernell_os_sdk.cli.demo import main as run
    elif cmd == "cloud":
        from kernell_os_sdk.cli.cloud import main as run
    elif cmd == "dashboard":
        from kernell_os_sdk.cli.dashboard import main as run
    elif cmd == "--help":
        print("Usage: kernell [init|doctor|demo|cloud|dashboard]")
        return 0
    else:
        print(f"Unknown command: {cmd}")
        return 1

    sys.exit(run())

if __name__ == "__main__":
    main()
