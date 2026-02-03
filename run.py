import os
import sys

port = os.environ.get("PORT", "8501")
print(f"Starting Streamlit on port {port}")

os.system(f"streamlit run app.py --server.port={port} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false")
