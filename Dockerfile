ARG VERSION=latest

FROM docker.io/library/python:${VERSION}
RUN apt-get update && apt-get upgrade -y

COPY / /opt/wandering_inn
WORKDIR /opt/wandering_inn
RUN pip install -r requirements.txt

VOLUME ["/opt/wandering_inn/build"]

ENTRYPOINT ["/opt/wandering_inn/wanderinginn2epub.py"]
CMD ["--output-by-chapter", "--chapter", "latest" ]

