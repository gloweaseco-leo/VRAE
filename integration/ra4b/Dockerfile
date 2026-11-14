ARG PYTHON_BASE=python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
FROM ${PYTHON_BASE}
WORKDIR /work
COPY requirements-ra1a.lock requirements-ra4a.lock requirements-ra4b-p1.lock /deps/
RUN python -m pip install --no-cache-dir -r /deps/requirements-ra4b-p1.lock && python -m pip check
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 PYTHONPATH=/work
CMD ["python", "integration/ra4b/runtime_check.py"]
