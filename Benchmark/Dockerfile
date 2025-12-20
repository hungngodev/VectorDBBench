FROM python:3.11-slim

WORKDIR /opt/vdb

COPY . /opt/vdb

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install --upgrade protobuf==6.31.1 && \
    pip install -e '.[vald,qdrant,weaviate]'

ENV DATASET_LOCAL_DIR=/opt/vdb/datasets
ENV PATH="/opt/vdb:${PATH}"

ENTRYPOINT ["bash", "-lc"]
