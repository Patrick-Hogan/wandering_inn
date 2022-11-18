ARG CALIBRE_VERSION=latest

FROM docker.io/linuxserver/calibre:${CALIBRE_VERSION}
RUN apt-get update && apt-get install -y --no-install-recommends git python3-pip

COPY / /opt/wandering_inn
WORKDIR /opt/wandering_inn
RUN git submodule init && git submodule update && pip install -r requirements.txt

VOLUME ["/opt/wandering_inn/build"]

ENTRYPOINT ["./entrypoint.sh"]

