# The review service (review.sustenaut.eu): Sustenaut/review-tooling's review-site/, at the
# release below, with pub and the start-up loader. The image holds no data: publication 0 and
# the paper extracts are private, so the pod's load container fetches them from storage when it
# starts (load.py), into a volume the app reads (REVIEW_BUNDLES). So the image is public.

# pub bundles the objects for names. It is the publet-cli release the extracts were signed with,
# which carries the concept sort.
FROM docker.io/library/rust:1-slim AS pub
ARG PUBLET_REV=v0.2.2
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/Sustenaut/publet.git /publet \
    && git -C /publet fetch --quiet origin "${PUBLET_REV}" \
    && git -C /publet checkout --quiet "${PUBLET_REV}"
WORKDIR /publet
RUN cargo build --release --locked -p publet-cli

# The service's code, at the release this image is pinned to.
FROM docker.io/library/debian:stable-slim AS code
ARG REVIEW_TOOLING_REV=v0.1.4
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${REVIEW_TOOLING_REV}" https://github.com/Sustenaut/review-tooling.git /src

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8080 \
    PUB=/usr/local/bin/pub REVIEW_BUNDLES=/app/bundles
WORKDIR /app
COPY --from=code /src/requirements.lock /src/review-site/requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt -c /tmp/requirements.lock
COPY --from=pub /publet/target/release/pub /usr/local/bin/pub
RUN useradd --create-home --uid 1000 app && install -d -o app /app/bundles
COPY --chown=app --from=code /src/review-site/review/ review/
COPY --chown=app load.py ./
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn review.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
