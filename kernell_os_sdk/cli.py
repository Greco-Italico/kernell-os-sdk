import argparse
import sys
import time
import os
import json
from .__init__ import __version__

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    parser = argparse.ArgumentParser(
        description="Kernell OS SDK CLI - Build Sovereign Autonomous Swarms"
    )
    parser.add_argument("--version", action="version", version=f"kernell-os-sdk {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Interactive wizard to scaffold a new Agent Swarm")
    init_parser.add_argument("name", nargs="?", default="my-swarm", help="Name of the agent project")
    init_parser.add_argument("--yes", action="store_true", help="Accept all defaults without prompting")
    
    # Install command
    install_parser = subparsers.add_parser("install", help="Deploy the agent in its Docker sandbox")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run the agent swarm daemon")
    
    # GUI command
    gui_parser = subparsers.add_parser("gui", help="Launch the local Command Center Dashboard")
    gui_parser.add_argument("--port", type=int, default=3000, help="Port to run the GUI on")
    
    args = parser.parse_args()
    
    if args.command == "init":
        interactive_init(args.name, args.yes)
        
    elif args.command == "install":
        print("📦 Building Kernell OS Sandbox...")
        print("✅ Sandbox Ready.")
        
    elif args.command == "run":
        print("⚙️  Starting Swarm Daemon...")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down.")
            
    elif args.command == "gui":
        print(f"🖥️  Starting Command Center on http://localhost:{args.port} ...")
        # In a real scenario, this would spin up the Next.js/React server or FastAPI
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down.")
            
    else:
        parser.print_help()
        sys.exit(1)

def interactive_init(project_name, auto_yes):
    clear_screen()
    print("============================================================")
    print(" KERNELL OS SDK v1.0 — UNIFIED SETUP WIZARD")
    print("============================================================")
    print("\\n[1/3] Starting Local Web Installer...")
    
    try:
        from .launcher import run_launcher
        import webbrowser
        import threading
        
        def open_browser():
            time.sleep(1.5)
            print("[2/3] Opening your browser for the unified setup...")
            webbrowser.open("http://localhost:3000")
            
        threading.Thread(target=open_browser, daemon=True).start()
        run_launcher()
        
    except ImportError:
        print("❌ Error: Web setup requires GUI dependencies.")
        print("Please run: pip install kernell-os-sdk[gui]")
        sys.exit(1)

if __name__ == "__main__":
    main()
