FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY app/ /app/

# Expose the port Flask runs on
EXPOSE 5012

# Make entrypoint.sh executable
RUN chmod +x /app/entrypoint.sh

# Run the startup script
ENTRYPOINT ["/app/entrypoint.sh"]
