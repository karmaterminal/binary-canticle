"""Shared settings for the ringserver proofs (ports come from the environment)."""

import os

HOST = os.environ.get("RS_HOST", "127.0.0.1")
DLPORT = int(os.environ.get("DLPORT", "16000"))  # DataLink-only listener
SLPORT = int(os.environ.get("SLPORT", "18000"))  # SeedLink + HTTP/WebSocket + DataLink listener
