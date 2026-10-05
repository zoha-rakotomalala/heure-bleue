"""Sign a release's SHA256SUMS.txt with the heure bleue Ed25519 key.

  HB_SIGNING_KEY=<base64 32-byte seed> python3 tools/sign_sums.py out/SHA256SUMS.txt

Writes SHA256SUMS.txt.sig (64 raw bytes) next to it, then checks the signature
against the public key compiled into heurebleue/updates.py, so a key that does
not match the app fails the release instead of shipping an update nobody can
install. Needs the `cryptography` package.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from heurebleue.updates import verify_signature  # noqa: E402


def main() -> int:
    seed_b64 = os.environ.get("HB_SIGNING_KEY", "").strip()
    if not seed_b64:
        print("HB_SIGNING_KEY is not set: add the release signing key as a repository secret", file=sys.stderr)
        return 2
    sums = Path(sys.argv[1])
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(seed_b64))
    message = sums.read_bytes()
    sig = key.sign(message)
    verify_signature(message, sig)  # raises if HB_SIGNING_KEY is not the key the app trusts
    (sums.with_name(sums.name + ".sig")).write_bytes(sig)
    print(f"signed {sums.name} ({len(message)} bytes) -> {sums.name}.sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
