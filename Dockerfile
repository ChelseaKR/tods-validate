# Digest-pinned so a build is reproducible and Renovate can keep it current
# (renovate.json extends helpers:pinGitHubActionDigestsToSemver; this is a
# regular image reference and picked up by Renovate's default docker manager
# too). Verified against the multi-arch index at push time:
#   docker buildx imagetools inspect python:3.13-slim
FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280

COPY . /src
RUN pip install --no-cache-dir /src && rm -rf /src

# Run as a non-root user (semgrep dockerfile.security.missing-user*): the
# image never needs root at runtime, so drop privileges before ENTRYPOINT.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin tods
USER tods

ENTRYPOINT ["tods-validate"]
CMD ["--help"]
