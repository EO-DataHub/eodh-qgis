FROM qgis/qgis:release-3_36

# Install required packages
# Constrain numpy for compatibility with scipy in QGIS base image
# Note: pandas is explicitly installed to ensure complete installation
# (prevents ModuleNotFoundError: No module named 'pandas._libs.pandas_parser')
RUN echo "numpy<1.25.0" > /tmp/constraints.txt && \
    pip3 install pyeodh pandas pytest pytest-cov pytest-qgis -c /tmp/constraints.txt

# Set the entrypoint script
COPY .docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"] 