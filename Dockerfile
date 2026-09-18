# Digest-pinned so a build is reproducible. Dependabot's `docker` ecosystem
# (.github/dependabot.yml) keeps the tag and the digest current. Verified
# against the multi-arch index at push time:
#   docker buildx imagetools inspect python:3.13-slim
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

COPY . /src
RUN pip install --no-cache-dir /src && rm -rf /src

# Run as a non-root user (semgrep dockerfile.security.missing-user*): the
# image never needs root at runtime, so drop privileges before ENTRYPOINT.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin tods
USER tods

ENTRYPOINT ["tods-validate"]
CMD ["--help"]
