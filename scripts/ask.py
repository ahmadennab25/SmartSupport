import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

message = sys.argv[1]
phone = sys.argv[2] if len(sys.argv) > 2 else "+962790000001"
url = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8000/api/chat/"

key = ""
for line in (Path(__file__).resolve().parent.parent / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("CHAT_API_KEY="):
        key = line.split("=", 1)[1].strip().strip("'\"")

sys.stdout.reconfigure(encoding="utf-8")
request = urllib.request.Request(
    url,
    data=json.dumps({"phone": phone, "message": message}).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8", "X-API-Key": key},
)
try:
    data = json.loads(urllib.request.urlopen(request, timeout=90).read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    sys.exit(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}")
except urllib.error.URLError as exc:
    sys.exit(f"Cannot reach the server: {exc.reason}")

print("reply      :", data["reply"])
print("tool_calls :", ", ".join(data["tool_calls"]) or "-")
print("latency_ms :", data["latency_ms"])
print("failed     :", data["failed"])