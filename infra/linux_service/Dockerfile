ARG RUNTIME_IMAGE=vrae-g1:313
FROM ${RUNTIME_IMAGE}
ARG SOURCE_SHA
LABEL vrae.source_sha=$SOURCE_SHA
COPY . /work
RUN printf "%s" "$SOURCE_SHA" > /work/infra/linux_service/source-sha
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 PYTHONPATH=/work
CMD ["python", "-m", "infra.linux_service.supervisor"]
