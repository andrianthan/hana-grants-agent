ARG FUNCTION_DIR="/function"

FROM python:3.12-slim AS build-image

ARG FUNCTION_DIR
RUN mkdir -p ${FUNCTION_DIR}

# Copy and install requirements first for Docker layer caching
COPY infrastructure/docker/evaluator/requirements.txt /tmp/requirements.txt
RUN pip3 install --target ${FUNCTION_DIR} -r /tmp/requirements.txt

# Copy function code
COPY scripts/evaluation/ ${FUNCTION_DIR}/evaluation/
COPY scripts/utils/ ${FUNCTION_DIR}/utils/
COPY org-materials/ ${FUNCTION_DIR}/org-materials/

# Production stage
FROM python:3.12-slim

ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "evaluation.handler.handler" ]
