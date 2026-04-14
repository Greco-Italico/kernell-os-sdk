#!/usr/bin/env python3
import sys
import json
import argparse
from kap_escrow.wal import TransactionWAL

def main():
    parser = argparse.ArgumentParser(description="Decode kap_escrow.wal.bin to JSONL for forensic audit.")
    parser.add_argument("wal_path", type=str, default="kap_escrow_wal.bin", nargs="?", help="Path to the binary WAL file")
    args = parser.parse_args()

    try:
        wal = TransactionWAL(args.wal_path)
    except Exception as e:
        print(f"Failed to load WAL: {e}", file=sys.stderr)
        sys.exit(1)

    # Verify integrity first
    is_valid, count = wal.verify_integrity()
    if not is_valid:
        print(f"WARNING: WAL Integrity verification failed at sequence count: {count}. The chain is broken or file is corrupted.", file=sys.stderr)
    
    # Dump via replay
    entries = wal.replay(since_seq=0)
    for entry in entries:
        print(json.dumps(entry, separators=(',', ':')))

    print(f"\n[INFO] Decoded {len(entries)} entries. Hash chain integrity: {'OK' if is_valid else 'FAILED'}", file=sys.stderr)

if __name__ == "__main__":
    main()
