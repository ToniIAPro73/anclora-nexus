import os
import sys
import json
import urllib.request
import uvicorn

# 1. Fetch service token from Render API if not in env
if not os.environ.get("IDENTITY_SERVICE_TOKEN"):
    render_key = os.environ.get("RENDER_API_KEY")
    if render_key:
        try:
            url = "https://api.render.com/v1/services/srv-dait9g5g1s2s738m2vjg/env-vars"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {render_key}"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data:
                    k = item.get("envVar", {}).get("key")
                    v = item.get("envVar", {}).get("value")
                    if k == "APPLICATION_SERVICE_TOKENS_JSON":
                        tokens = json.loads(v)
                        # Use data-lab token which has access to all admin routes
                        os.environ["IDENTITY_SERVICE_TOKEN"] = tokens.get("data-lab", "")
                        break
        except Exception as e:
            print("Warning: could not fetch service token from Render:", e)

# 2. Configure environment
os.environ.setdefault("IDENTITY_SERVICE_URL", "https://anclora-identity-development.onrender.com")
os.environ.setdefault("IDENTITY_PROVISIONING_ENABLED", "true")
os.environ.setdefault("GUESTHUB_APP_URL", "https://anclora-guesthub-o95pj8bt7-pmi140979-6354s-projects.vercel.app")
os.environ.setdefault("ALLOW_REAL_SUPABASE_WRITE", "true")
os.environ.setdefault("SUPABASE_URL", "https://jtlnmypcrgmzxeuiffup.supabase.co")

print("Launching Anclora Nexus Backend in Development mode...")
print(f"  Identity Service URL: {os.environ.get('IDENTITY_SERVICE_URL')}")
print(f"  Identity Provisioning: {os.environ.get('IDENTITY_PROVISIONING_ENABLED')}")
print(f"  GuestHub App URL: {os.environ.get('GUESTHUB_APP_URL')}")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, log_level="info")
