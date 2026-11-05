# syntax=docker/dockerfile:1
# The named `maya` build context is the existing pinned source checkout.
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates git python3 python3-venv ninja-build \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/maya
COPY --from=maya . /opt/maya/
RUN test "$(git rev-parse HEAD)" = c4effee67cb95fb4303720919b075fddf04b4e69 \
    && test -z "$(git status --porcelain --untracked-files=all -- serve tools/maya_names.py tools/maya_quants.py tools/strata_tokenizer.py)" \
    && test -z "$(git status --porcelain --untracked-files=all -- src include cmake third_party CMakeLists.txt)" \
    && python3 -m venv /opt/build-tools \
    && /opt/build-tools/bin/pip install --no-cache-dir cmake==4.4.3 \
    && /opt/build-tools/bin/cmake -S /opt/maya -B /opt/maya-build -G Ninja \
       -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120 \
       -DMAYA_ENABLE_CUDA=ON -DMAYA_BUILD_TESTS=OFF -DMAYA_NATIVE_EXPERTS=OFF \
       -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    && /opt/build-tools/bin/cmake --build /opt/maya-build --target maya-ds4 --parallel 2

FROM nvidia/cuda:13.0.0-runtime-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 LANG=C.UTF-8 \
    MAYA_PYTHON=/opt/deployment/.venv/bin/python MAYA_SOURCE_DIR=/opt/maya \
    MAYA_ENGINE=/opt/engine/maya-ds4 MAYA_CONTAINER=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 python3-venv libatomic1 libgomp1 util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/deployment
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir \
    regex==2026.9.10 jinja2==3.1.6 pyyaml==6.0.3 psutil==7.2.2
COPY --from=build /opt/maya /opt/maya
COPY --from=build /opt/maya-build/maya-ds4 /opt/engine/maya-ds4
COPY deployment/env.sh deployment/maya_local.py deployment/docker-entrypoint.sh deployment/
COPY install.sh start.sh check.sh smoke-test.sh ./
HEALTHCHECK --interval=15s --timeout=5s --start-period=300s --retries=3 \
    CMD ["/opt/deployment/.venv/bin/python", "-c", "import json,os,urllib.request; p=os.environ.get('DS41_PORT','8081'); k=os.environ.get('STRATA_API_KEY',''); r=urllib.request.Request('http://127.0.0.1:'+p+'/health',headers={'Authorization':'Bearer '+k} if k else {}); h=json.load(urllib.request.urlopen(r,timeout=4)); assert h.get('status')=='ok' and not h.get('unloaded')"]
ENTRYPOINT ["bash", "/opt/deployment/deployment/docker-entrypoint.sh"]
