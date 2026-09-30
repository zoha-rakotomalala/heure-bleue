"""Render a URL with headless Chrome under a hard timeout. Usage: render.py URL OUT.png WxH"""
import subprocess, sys, tempfile
url, out, size = sys.argv[1], sys.argv[2], sys.argv[3]
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
with tempfile.TemporaryDirectory() as prof:
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
           f"--window-size={size}", "--virtual-time-budget=9000", f"--screenshot={out}", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print("exit", r.returncode, "->", out)
    except subprocess.TimeoutExpired:
        print("TIMEOUT after 60s, no screenshot"); sys.exit(1)
