FROM qgis/qgis:release-3_36

# Install required packages
RUN pip3 install pyeodh pytest pytest-cov pytest-qgis

# Set the entrypoint script
COPY .docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"] 