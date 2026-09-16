ARG QGIS_IMAGE=qgis/qgis:4.2-trixie
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
