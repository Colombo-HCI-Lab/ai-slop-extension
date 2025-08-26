# =============================================================================
# SlowFast Video Detection API — 3-Stage Build with Optimal Layer Caching
# -----------------------------------------------------------------------------
# - Stage 1 (base): System packages and tools that rarely change
# - Stage 2 (deps): Python dependencies that change less frequently  
# - Stage 3 (runtime): Application code that changes frequently
# This maximizes Docker layer caching for faster rebuilds during development.
# =============================================================================

# ---- Stage 1: Base system packages (rarely changes) ------------------------
FROM python:3.10-slim-bookworm AS base

# Sensible defaults for Python apps in containers
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV="/app/.venv" \
    PATH="/root/.local/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# Install system packages needed for building and runtime
# These rarely change, so this layer will be cached most of the time
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools (needed for dependency compilation)
    build-essential \
    cmake \
    git \
    pkg-config \
    curl \
    # Development headers for media libraries
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    # Runtime libraries for media processing
    ffmpeg \
    libglib2.0-0 \
    libgl1 \
    libgstreamer1.0-0 \
    libmagic1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv (modern Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Create the virtual environment in a fixed path
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create non-root user (do this early since it rarely changes)
RUN useradd --create-home --shell /bin/bash app


# ---- Stage 2: Dependencies (changes less frequently) -----------------------
FROM base AS deps

# Copy only dependency files first (triggers rebuild only when deps change)
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
# This layer will be cached unless pyproject.toml or uv.lock changes
RUN . "$VIRTUAL_ENV/bin/activate" && uv sync --frozen --no-install-project


# ---- Stage 3: Application code (changes frequently) ------------------------
FROM deps AS runtime

# Copy application source code (this layer rebuilds on every code change)
COPY --chown=app:app . .

# Copy GCS credentials if available (for Cloud Run deployment)
COPY --chown=app:app gcs-key.json* /app/

# Install the project itself (editable install for the current project)
RUN . "$VIRTUAL_ENV/bin/activate" && uv sync --frozen

# Ensure required folders exist and are writable at runtime
RUN mkdir -p backend/uploads backend/models backend/logs logs && \
    chown -R app:app /app

# Optional: precompile Python bytecode for faster cold starts
RUN python -m compileall -q /app

# Drop privileges to non-root user
USER app

# Ensure the virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Default port for local/dev. Platforms like Cloud Run will inject $PORT.
ENV PORT=8000

# Document the port; EXPOSE is informational for most orchestrators
EXPOSE 8000

# Simple liveness check that hits your FastAPI/Starlette health endpoint
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f "http://localhost:${PORT}/api/v1/health" || exit 1

# Run uvicorn as Python module from the venv (no shell activation needed)
# Use shell to expand PORT variable, then exec to proper signal handling
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 4"]
