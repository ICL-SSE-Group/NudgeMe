# Use Python base image
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Download Cloud SQL Proxy
RUN curl -o cloud_sql_proxy https://storage.googleapis.com/cloudsql-proxy/v1.33.7/cloud_sql_proxy.linux.amd64 && \
    chmod +x cloud_sql_proxy

# Expose port 8080 (required for Cloud Run)
EXPOSE 8080

# Start Cloud SQL Proxy in the background, then run Gunicorn
CMD ./cloud_sql_proxy -dir=/cloudsql -instances=nudgeme-450123:us-central1:database-expense=tcp:5432 & \
    gunicorn -b 0.0.0.0:8080 main:app





