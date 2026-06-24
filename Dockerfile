# Standalone PRISM dataset validator image.
#
# Packages only the validation engine (app/prism.py and its src/ + app/src/
# import closure) - no Flask, pandas, datalad, or other Studio app/converter
# dependencies. Intended for CI usage, e.g.:
#
#   docker build -t prism-validator .
#   docker run --rm --user "$(id -u):$(id -g)" -v "$(pwd)":/data prism-validator /data --json
FROM python:3.13-slim

WORKDIR /opt/prism

COPY requirements-validator.txt .
RUN pip install --no-cache-dir -r requirements-validator.txt

# Preserve the repo-relative layout: app/src/__init__.py and src/__init__.py
# merge their namespace package paths based on this exact directory structure.
COPY src/ ./src/
COPY app/prism.py ./app/prism.py
COPY app/src/ ./app/src/
COPY app/schemas/ ./app/schemas/

ENV PRISM_SKIP_VENV_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "app/prism.py"]
CMD ["--help"]
