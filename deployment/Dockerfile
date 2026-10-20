# syntax=docker/dockerfile:1
# Build THIS checkout, including local 1017 work, never an unrelated upstream HEAD.
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates python3 python3-venv ninja-build \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/strata
COPY Strata/ Strata/
COPY deployment/cmake/ deployment/cmake/
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir cmake==4.4.3 \
    && .venv/bin/cmake -S deployment/cmake -B build -G Ninja \
       -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120 \
       -DSTRATA_DS41_SOURCE=/opt/strata/Strata -DSTRATA_DS41_1017=ON -DSTRATA_DS41_STAGE_TESTS=OFF \
    && .venv/bin/cmake --build build --target ds41_serve --parallel 2

FROM nvidia/cuda:13.0.0-runtime-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 LANG=C.UTF-8 \
    DS41_PYTHON=/opt/strata/.venv/bin/python DS41_ENGINE=/opt/strata/engine/ds41_serve
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-venv libatomic1 libgomp1 util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/strata
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir \
    regex==2026.9.10 jinja2==3.1.6 pyyaml==6.0.3 psutil==7.2.2
COPY --from=build /opt/strata/build/bin/ds41_serve /opt/strata/engine/ds41_serve
COPY Strata/serve Strata/serve
COPY Strata/tools Strata/tools
COPY Strata/ds41/proto Strata/ds41/proto
COPY deployment/local_serve.py deployment/local_serve.py
COPY deployment/env.sh deployment/env.sh
COPY start.sh check.sh smoke-test.sh ./
HEALTHCHECK --interval=15s --timeout=5s --start-period=300s --retries=3 \
    CMD ["/opt/strata/.venv/bin/python", "-c", "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8081/health',timeout=4))['loaded']"]
ENTRYPOINT ["bash", "/opt/strata/start.sh"]
