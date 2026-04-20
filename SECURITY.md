# Security Policy

## Supported Versions

| Version | Security Updates |
|---------|-----------------|
| `main` / latest | ✅ Active |
| Older releases  | ⚠️ Best effort |

## Reporting a Vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Vulnerabilities in the Kernell OS SDK may affect wallets, escrow contracts,
and M2M payment flows. Responsible disclosure protects users while we work on a fix.

### How to Report

Send an encrypted email to **security@kernell.site** with:

1. **Description** — What is the vulnerability and where is it located?
2. **Reproduction steps** — Minimal code or commands to trigger it.
3. **Impact** — What can an attacker accomplish? (RCE, key extraction, fund loss, etc.)
4. **Severity estimate** — Your assessment (Critical / High / Medium / Low).
5. **Optional: suggested fix** — If you have one, we welcome it.

You may encrypt your report with our PGP key (available at `https://kernell.site/.well-known/security.txt`).

### Response Timeline

| Milestone | Target |
|-----------|--------|
| Acknowledgment | 48 hours |
| Initial assessment | 5 business days |
| Fix / mitigation | 30 days (critical), 90 days (others) |
| Public disclosure | Coordinated with reporter |

We follow a **coordinated disclosure** model. We will not take legal action
against researchers who follow this policy.

## Scope

**In scope:**
- `kernell_os_sdk/` Python package
- `kap_escrow/` escrow contract logic
- Rust crates under `src/`
- Docker / Firecracker sandbox isolation
- Cryptographic implementation (wallet, KDF, signing)
- Web installer (`kernell init`)
- Any dependency with a direct exploit path in our context

**Out of scope:**
- Vulnerabilities in underlying infrastructure we don't control (Docker daemon bugs, OS kernel CVEs)
- Social engineering attacks
- Denial of service via resource exhaustion without a specific bypass of our limits
- Issues already reported in our public issue tracker

## Security Design Principles

- **Zero-trust sandbox**: code runs in Docker with `--cap-drop=ALL`, no network, read-only FS.
- **AES-256-GCM** for private key encryption with Scrypt KDF.
- **AST-based validation** before any code reaches the runtime.
- **HMAC-SHA256 + anti-replay** on the Firecracker VSOCK channel.
- **Automatic secret redaction** in all structured logs.

## Known Limitations

- `SubprocessRuntime` is intentionally disabled in production. Do not re-enable it.
- The AST validator does not catch all possible Python sandbox escapes. Always
  pair it with OS-level isolation (Docker or Firecracker).
- The in-memory nonce store resets on process restart. For distributed deployments,
  use a shared Redis store with TTL.

## Hall of Fame

We thank the following researchers for responsible disclosure:

*(none yet — be the first!)*
