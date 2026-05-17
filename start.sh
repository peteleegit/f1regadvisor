#!/bin/bash
set -e

mkdir -p /app/.streamlit

cat > /app/.streamlit/secrets.toml <<EOF
[auth]
password = "${APP_PASSWORD}"

[anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[fiaruler]
api_url = "${F1REG_FIARULER_API_URL}"
api_key = "${F1REG_FIARULER_API_KEY}"
EOF

exec streamlit run app.py \
    --server.port "${PORT:-8501}" \
    --server.address 0.0.0.0 \
    --server.headless true
