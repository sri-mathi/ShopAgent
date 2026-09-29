FROM python:3.12-slim

WORKDIR /app

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

EXPOSE 8000
CMD ["uvicorn", "shopagent_core.main:app", "--host", "0.0.0.0", "--port", "8000"]
