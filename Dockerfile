# Kernell OS: Entorno de Pruebas de 1-Click
FROM python:3.11-slim

# Metadatos
LABEL maintainer="Kernell OS Foundation"
LABEL version="0.1.0-alpha"
LABEL description="Kernell OS M2M Agent Environment"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KERNELL_ENV="docker-alpha"

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir .

# Copiar el SDK y los Demos
COPY kernell_os_sdk/ kernell_os_sdk/
COPY demo_*.py ./

# Usuario no-root para seguridad
RUN useradd -m kernell_agent && chown -R kernell_agent:kernell_agent /app
USER kernell_agent

# Punto de entrada predeterminado mostrando la CLI o ejecutando un demo
CMD ["python", "demo_phase4_sovereignty.py"]
