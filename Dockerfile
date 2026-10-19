ARG QGIS_IMAGE=qgis/qgis:4.2-trixie@sha256:56c69c92e316aa679e5c30ebf7fcfd89fd1124ec728106ec0cced1c71a28d877
FROM ${QGIS_IMAGE}

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-gdal python3-numpy python3-pytest python3-pytest-cov && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
ENV QT_QPA_PLATFORM=offscreen \
    QGIS_PREFIX_PATH=/usr \
    PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins
ENTRYPOINT ["python3"]
CMD ["-m", "pytest", "tests", "--cov=eodh_qgis", "--cov-report=term-missing", "--cov-report=xml", "--junitxml=test-results.xml"]
