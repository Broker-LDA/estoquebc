"""Sonda interna usa o Host público permitido sem depender de DNS/TLS externos."""
import os
import sys
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

try:
    host = urlsplit(os.environ['PUBLIC_BASE_URL']).netloc
    request = Request(f"http://127.0.0.1:{int(os.getenv('PORT', '8000'))}/healthz", headers={'Host': host})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
