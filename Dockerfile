ARG QGIS_IMAGE=qgis/qgis:4.2-trixie@sha256:2752326202b7df66387c2073c39d6d6a1e8f59418b199a11b88276089dc355a8
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
