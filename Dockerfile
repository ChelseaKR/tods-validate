FROM python:3.13-slim

COPY . /src
RUN pip install --no-cache-dir /src && rm -rf /src

ENTRYPOINT ["tods-validate"]
CMD ["--help"]
