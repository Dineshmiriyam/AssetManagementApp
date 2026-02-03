import os
import subprocess
import sys

# Get PORT from environment, default to 8501
port = os.environ.get("PORT", "8501")

# Debug: print all env vars related to port
print(f"PORT env var: {port}")
print(f"All PORT-related vars:")
for key, value in os.environ.items():
    if "PORT" in key.upper():
        print(f"  {key}={value}")

# Ensure port is a valid integer
try:
    port_int = int(port)
except ValueError:
    print(f"Invalid PORT value: {port}, using 8501")
    port_int = 8501

print(f"Starting Streamlit on port {port_int}")

# Run streamlit with subprocess
cmd = [
    sys.executable, "-m", "streamlit", "run", "app.py",
    f"--server.port={port_int}",
    "--server.address=0.0.0.0",
    "--server.headless=true",
    "--server.enableCORS=false",
    "--server.enableXsrfProtection=false"
]

print(f"Running command: {' '.join(cmd)}")
subprocess.run(cmd)
