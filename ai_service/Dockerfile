# Use Python 3.9 image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 5001
EXPOSE 5001

# Command to start the service
CMD ["python", "ai_service.py"]
