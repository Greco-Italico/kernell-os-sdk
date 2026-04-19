FROM python:3.11-slim

# Create isolated user for strict sandbox
RUN useradd -ms /bin/bash agent_user

WORKDIR /app

# Copy the SDK wheel and requirements
COPY kernell_os_sdk-1.0.0-py3-none-any.whl .
COPY main.py .
COPY .env .

# Install dependencies and SDK
RUN pip install --no-cache-dir ./kernell_os_sdk-1.0.0-py3-none-any.whl python-dotenv psutil fastapi uvicorn

# Ensure strict permissions
RUN chown -R agent_user:agent_user /app

# Drop to unprivileged user
USER agent_user

# Run the agent
CMD ["python", "main.py"]
