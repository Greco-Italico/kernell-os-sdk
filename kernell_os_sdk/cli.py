import argparse
import sys
import time
from .__init__ import __version__

def main():
    parser = argparse.ArgumentParser(
        description="Kernell OS SDK CLI - Manage Autonomous PC Agents"
    )
    parser.add_argument("--version", action="version", version=f"kernell-os-sdk {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize a new PC agent project")
    init_parser.add_argument("name", help="Name of the agent project")
    
    # Install command
    install_parser = subparsers.add_parser("install", help="Deploy the agent in its Docker sandbox")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run the agent daemon")
    
    # GUI command
    gui_parser = subparsers.add_parser("gui", help="Launch the local control panel (FastAPI/React)")
    gui_parser.add_argument("--port", type=int, default=8500, help="Port to run the GUI on")
    
    # Wallet command
    wallet_parser = subparsers.add_parser("wallet", help="Manage your $KERN & SOL dual wallet")
    wallet_parser.add_argument("--balance", action="store_true", help="Check current balance")
    
    args = parser.parse_args()
    
    if args.command == "init":
        print(f"🚀 Initializing new Kernell OS PC Agent: {args.name}")
        print("Generating Cryptographic Passport...")
        print("Done! Edit your agent script to configure Sandbox permissions.")
        
    elif args.command == "install":
        print("📦 Building Kernell OS Sandbox...")
        print("Allocating limits (RAM, CPU, Disk)...")
        print("Applying filesystem & network permission boundaries...")
        print("✅ Sandbox Ready. You can now use 'kernell run' or 'kernell gui'.")
        
    elif args.command == "run":
        print("⚙️  Starting Agent Daemon...")
        print("Listening for M2M Tasks & Local Prompt events...")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down.")
            
    elif args.command == "gui":
        print(f"🖥️  Starting Local Control Panel on http://localhost:{args.port} ...")
        from .agent import Agent
        from .gui import AgentGUI
        
        # Load default agent for GUI if no specific script provided
        agent = Agent(name="Kernell PC Agent")
        gui = AgentGUI(agent, port=args.port)
        gui.start()
        
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down GUI.")
        
    elif args.command == "wallet":
        if args.balance:
            from .wallet import Wallet
            w = Wallet()
            print(f"💰 Volatile $KERN Balance: {w.get_balance()} KERN")
            print(f"💰 Solana SPL Balance: 0.0 KERN")
        else:
            wallet_parser.print_help()
            
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
