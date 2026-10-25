# Data architecture

The only implemented data layer is PostgreSQL source configuration, documented in the data dictionary. No datasets are collected or exported.

Future architecture: Jetstream observations enter an idempotent operational store; separate batch jobs produce Bronze/Silver/Gold Delta/Parquet datasets. PostgreSQL serves low-latency application queries, while historical processing and training consume reproducible snapshots. The exact synchronization contract, retention, deletion propagation, partitioning and quality gates will be implemented with those milestones. Spark and Databricks are not website dependencies.
