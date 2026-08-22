# Kubernetes deployment status
The checked-in manifest is intentionally single-replica. The current reference control plane uses SQLite and a local durable CAS; running multiple active replicas against those files would be unsafe. HA/multi-region deployment is gated on the later transactional metadata/object backend implementation and must not be enabled by simply increasing `replicas`.
