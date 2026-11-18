ARG DEPENDENCY_IMAGE=vrae-ra4b-p1:313
FROM ${DEPENDENCY_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends iptables iproute2 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 PYTHONPATH=/work
CMD ["python", "-m", "integration.l2_launch.g1.supervisor"]
