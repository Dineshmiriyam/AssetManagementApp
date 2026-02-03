FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Default port (Railway overrides this)
ENV PORT=8501

# Create startup script
RUN echo '#!/bin/bash\nstreamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false' > /app/start.sh && chmod +x /app/start.sh

# Run with shell to expand variables
CMD ["/bin/bash", "/app/start.sh"]
