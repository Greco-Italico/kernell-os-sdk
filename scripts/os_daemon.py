"""
Kernell OS — OS Control Daemon (Phase 7b)
═════════════════════════════════════════
Isolated microservice that bridges the agent's virtual commands to physical UI interactions.
Must be run inside the sandboxed environment (e.g. Xvfb container).

Features:
- Bounding Box Restriction
- Rate Limiting
- Fail-closed execution
- Mock fallback for environments without displays
"""

import base64
import io
import time
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("os_daemon")

app = FastAPI(title="Kernell OS Control Daemon")

# ── Hardware Interaction ──────────────────────────────────────────
# Graceful fallback if not running in a UI environment
HAS_UI = False
try:
    import pyautogui
    from PIL import ImageGrab
    pyautogui.FAILSAFE = False  # Controlled by our own bounds check
    HAS_UI = True
    logger.info("Hardware UI modules loaded successfully.")
except ImportError:
    logger.warning("pyautogui / PIL not found. Running in MOCK mode.")

# ── Security & Policy ─────────────────────────────────────────────
ALLOWED_AREA = (0, 0, 1920, 1080)  # x_min, y_min, x_max, y_max
MAX_ACTIONS_PER_SECOND = 5

class RateLimiter:
    def __init__(self, limit_per_sec: int):
        self.limit = limit_per_sec
        self.calls = []

    def check(self):
        now = time.time()
        # Keep only calls from the last second
        self.calls = [t for t in self.calls if now - t < 1.0]
        if len(self.calls) >= self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Too many UI actions.")
        self.calls.append(now)

rate_limiter = RateLimiter(MAX_ACTIONS_PER_SECOND)

def enforce_bounds(x: int, y: int):
    """Ensure coordinates are within the safe sandbox display area."""
    if not (ALLOWED_AREA[0] <= x <= ALLOWED_AREA[2] and ALLOWED_AREA[1] <= y <= ALLOWED_AREA[3]):
        logger.error(f"Action blocked: Coordinates ({x}, {y}) out of bounds.")
        raise HTTPException(status_code=403, detail="Coordinates out of allowed sandbox bounds.")

# ── API Models ────────────────────────────────────────────────────
class ClickRequest(BaseModel):
    x: int
    y: int
    session_id: Optional[str] = None

class TypeRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

class KeypressRequest(BaseModel):
    key: str
    session_id: Optional[str] = None

# ── Endpoints ─────────────────────────────────────────────────────

@app.post("/click")
def handle_click(req: ClickRequest):
    rate_limiter.check()
    enforce_bounds(req.x, req.y)
    
    logger.info(f"OS Click at ({req.x}, {req.y})")
    if HAS_UI:
        pyautogui.moveTo(req.x, req.y, duration=0.2)
        pyautogui.click()
    return {"success": True, "action": "click", "x": req.x, "y": req.y}


@app.post("/type")
def handle_type(req: TypeRequest):
    rate_limiter.check()
    
    # Simple sanitization
    if len(req.text) > 1000:
        raise HTTPException(status_code=400, detail="Text payload too large.")
        
    logger.info(f"OS Type: {req.text[:20]}...")
    if HAS_UI:
        pyautogui.write(req.text, interval=0.01)
    return {"success": True, "action": "type", "length": len(req.text)}


@app.post("/keypress")
def handle_keypress(req: KeypressRequest):
    rate_limiter.check()
    
    # Whitelist safe keys
    allowed_keys = {'enter', 'tab', 'escape', 'space', 'backspace', 'up', 'down', 'left', 'right'}
    if req.key.lower() not in allowed_keys:
        raise HTTPException(status_code=403, detail=f"Key '{req.key}' is not in the allowed safe whitelist.")
        
    logger.info(f"OS Keypress: {req.key}")
    if HAS_UI:
        pyautogui.press(req.key.lower())
    return {"success": True, "action": "keypress", "key": req.key}


@app.get("/screenshot")
def handle_screenshot(request: Request):
    rate_limiter.check()
    session_id = request.headers.get("X-Session-ID", "default")
    logger.info(f"OS Screenshot for session: {session_id}")
    
    if HAS_UI:
        try:
            img = ImageGrab.grab(bbox=ALLOWED_AREA)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return {"success": True, "image_base64": b64}
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to capture screen.")
            
    # Mock fallback
    return {"success": True, "image_base64": "mock_base64_string_due_to_missing_ui_libs"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting OS Control Daemon on port 8505...")
    uvicorn.run(app, host="0.0.0.0", port=8505)
