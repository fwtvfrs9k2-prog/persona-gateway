# Combined persona-gateway + sub2api image for Render.
# Build/deploy this from a Git repo on Render (Web Service -> Git, Dockerfile).
# Keep all existing Neon/Upstash env vars from the current sub2api service;
# do NOT re-run auto-setup that would overwrite the existing admin account.
FROM weishaw/sub2api:latest
USER root
RUN apt-get update && apt-get install -y python3 python3-pip procps curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app-gateway
COPY gateway.py requirements.txt start.sh ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt \
    && chmod +x start.sh
CMD ["sh", "./start.sh"]
