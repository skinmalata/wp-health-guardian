import os
import asyncio
import sys

# Force aiohttp to use ThreadedResolver instead of async DNS resolver
# This fixes "Could not contact DNS servers" on Windows
try:
    import aiohttp.resolver as ar
    ar.AsyncResolver = ar.ThreadedResolver
except Exception:
    pass

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from web.server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
