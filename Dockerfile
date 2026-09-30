FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY business_discovery ./business_discovery
COPY assets ./assets
RUN pip install --no-cache-dir .
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-c", "from business_discovery.api import serve; serve(host='0.0.0.0')"]
