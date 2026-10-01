FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app
# Keep the embedding model's download cache inside /app, not root's default
# ~/.cache - everything under /app gets chown'd to the non-root user below,
# so this avoids a separate permission fix for a second directory.
ENV HF_HOME=/app/.cache/huggingface

COPY requirements.txt .

# Install the CPU-only torch build first, from PyTorch's own index - the
# default PyPI wheel bundles full NVIDIA CUDA/GPU support (multiple GB of
# nvidia-* packages) that this container has no use for, since it only ever
# runs a small embedding model on CPU. Installing it first means the later
# `pip install -r requirements.txt` sees torch already satisfied and never
# pulls the GPU variant in as a transitive dependency of sentence-transformers.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY shopagent_core/ shopagent_core/

# Run as a non-root user - if a dependency vulnerability were ever exploited,
# this limits what the process can do to the container's own filesystem.
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Many hosting platforms (Render, Railway, Heroku-style) assign the listen
# port dynamically via $PORT at container *runtime*, not build time - a
# hardcoded port fails every deploy on those platforms regardless of whether
# the app itself works. ${PORT:-8000} falls back to 8000 for local
# docker-compose use, where PORT is never set.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Shell form (not exec-array form) so ${PORT:-8000} actually gets expanded -
# but a bare shell-form CMD makes /bin/sh PID 1, which does NOT reliably
# forward SIGTERM to uvicorn, causing ungraceful shutdowns. `exec` replaces
# the shell process with uvicorn itself, so uvicorn becomes PID 1 and
# receives signals directly.
CMD ["sh", "-c", "exec uvicorn shopagent_core.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
