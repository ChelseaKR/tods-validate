# For reproducible CI, pin by digest at release time:
#   FROM python:3.13-slim@sha256:<digest>
FROM python:3.13-slim

COPY . /src
RUN pip install --no-cache-dir /src && rm -rf /src

ENTRYPOINT ["tods-validate"]
CMD ["--help"]
