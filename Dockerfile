ARG CALIBRE_VERSION=latest

FROM docker.io/linuxserver/calibre:${CALIBRE_VERSION}
RUN apt update && apt install -y git python3-pip

COPY / /opt/wandering_inn
WORKDIR /opt/wandering_inn
RUN git submodule init && git submodule update
RUN pip3 install -r requirements.txt

VOLUME ["/opt/wandering_inn/build"]

ENTRYPOINT ["./entrypoint.sh"]

