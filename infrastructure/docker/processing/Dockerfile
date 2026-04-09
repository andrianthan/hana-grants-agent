ARG FUNCTION_DIR="/function"

FROM python:3.13-slim AS build-image

ARG FUNCTION_DIR
RUN mkdir -p ${FUNCTION_DIR}

# Install requirements
COPY scripts/requirements.txt /tmp/requirements.txt
RUN pip3 install --target ${FUNCTION_DIR} -r /tmp/requirements.txt

# Install Lambda runtime interface client
RUN pip3 install --target ${FUNCTION_DIR} awslambdaric

# Copy function code
COPY scripts/scrapers/ ${FUNCTION_DIR}/scrapers/
COPY scripts/utils/ ${FUNCTION_DIR}/utils/

# Production stage
FROM python:3.13-slim

ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "scrapers.processing.processing_handler.handler" ]
