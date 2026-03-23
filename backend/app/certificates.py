"""TLS certificate management — upload custom certs or generate via Let's Encrypt."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger()

CERT_DIR = Path("/app/certs")
CERT_FILE = CERT_DIR / "server.crt"
KEY_FILE = CERT_DIR / "server.key"


def get_cert_info() -> dict:
    """Get info about the currently installed certificate."""
    if not CERT_FILE.exists():
        return {"installed": False}

    try:
        import ssl

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))

        # Parse cert with openssl
        result = subprocess.run(
            ["openssl", "x509", "-in", str(CERT_FILE), "-noout", "-subject", "-issuer", "-dates", "-serial"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info = {"installed": True, "cert_path": str(CERT_FILE), "key_path": str(KEY_FILE)}

        for line in result.stdout.strip().split("\n"):
            if line.startswith("subject="):
                info["subject"] = line[8:].strip()
            elif line.startswith("issuer="):
                info["issuer"] = line[7:].strip()
            elif line.startswith("notBefore="):
                info["valid_from"] = line[10:].strip()
            elif line.startswith("notAfter="):
                info["valid_until"] = line[9:].strip()
            elif line.startswith("serial="):
                info["serial"] = line[7:].strip()

        # Check if self-signed
        info["self_signed"] = info.get("subject") == info.get("issuer")

        return info
    except Exception as e:
        return {"installed": True, "error": str(e)}


def save_certificate(cert_pem: str, key_pem: str) -> dict:
    """Save uploaded certificate and key PEM files."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    # Validate cert
    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", "/dev/stdin", "-noout", "-text"],
            input=cert_pem,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {"error": "Invalid certificate PEM format"}
    except Exception:
        pass  # openssl might not be available, skip validation

    # Validate key
    try:
        result = subprocess.run(
            ["openssl", "rsa", "-in", "/dev/stdin", "-check", "-noout"],
            input=key_pem,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {"error": "Invalid private key PEM format"}
    except Exception:
        pass

    # Write files
    CERT_FILE.write_text(cert_pem)
    KEY_FILE.write_text(key_pem)
    os.chmod(str(KEY_FILE), 0o600)

    logger.info("certificate_saved", cert=str(CERT_FILE))
    return {"message": "Certificate saved. Restart nginx to apply.", **get_cert_info()}


def generate_self_signed(hostname: str = "getvul.local", days: int = 365) -> dict:
    """Generate a self-signed certificate for testing."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(KEY_FILE),
                "-out",
                str(CERT_FILE),
                "-days",
                str(days),
                "-nodes",
                "-subj",
                f"/CN={hostname}/O=GetVul/C=US",
                "-addext",
                f"subjectAltName=DNS:{hostname},DNS:localhost,IP:127.0.0.1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {"error": f"OpenSSL failed: {result.stderr}"}

        os.chmod(str(KEY_FILE), 0o600)
        logger.info("self_signed_cert_generated", hostname=hostname)
        return {"message": f"Self-signed certificate generated for {hostname}", **get_cert_info()}
    except FileNotFoundError:
        return {"error": "OpenSSL not found. Install openssl to generate certificates."}
    except Exception as e:
        return {"error": str(e)}


def delete_certificate() -> dict:
    """Remove the installed certificate."""
    removed = False
    if CERT_FILE.exists():
        CERT_FILE.unlink()
        removed = True
    if KEY_FILE.exists():
        KEY_FILE.unlink()
        removed = True
    return {"message": "Certificate removed" if removed else "No certificate installed"}
