ARG FUNCTION_DIR="/function"

FROM mcr.microsoft.com/playwright/python:v1.58.0-noble AS build-image

ARG FUNCTION_DIR
RUN mkdir -p ${FUNCTION_DIR}

# Install only Chromium (not all browsers) — per Pitfall 2
RUN playwright install chromium

# Copy and install requirements first for Docker layer caching
COPY scripts/scrapers/requirements.txt /tmp/requirements.txt
RUN pip3 install --target ${FUNCTION_DIR} -r /tmp/requirements.txt

# Install Lambda runtime interface client
RUN pip3 install --target ${FUNCTION_DIR} awslambdaric

# Copy function code
COPY scripts/scrapers/ ${FUNCTION_DIR}/scrapers/
COPY scripts/utils/ ${FUNCTION_DIR}/utils/
COPY scraper_registry.json ${FUNCTION_DIR}/

# Production stage
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "scrapers.handler.handler" ]
