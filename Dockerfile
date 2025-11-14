FROM python:3.11-slim

WORKDIR /opt/vdb

COPY . /opt/vdb

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install -e '.[vald,qdrant,weaviate]'

ENV DATASET_LOCAL_DIR=/opt/vdb/datasets
ENV PATH="/opt/vdb:${PATH}"

ENTRYPOINT ["bash", "-lc"]
CMD ["./prepare_datasets.sh ${DATASET_LOCAL_DIR} && ./run_vector_benchmark.sh vectordb_bench/config-files/k8s_local_fourdb.yml"]
