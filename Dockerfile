FROM qgis/qgis:release-3_36

# Install required packages
# Constrain numpy for compatibility with scipy in QGIS base image
RUN echo "numpy<1.25.0" > /tmp/constraints.txt && \
    pip3 install pyeodh pytest pytest-cov pytest-qgis -c /tmp/constraints.txt

# Set the entrypoint script
COPY .docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"] 