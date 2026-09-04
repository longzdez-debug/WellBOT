# Store seam deferred until a second adapter exists

`DatabaseService` is a concrete class that builds its own Postgres pool and reads `schema.sql` from disk; callers hold the concrete type. Per the one-adapter rule ("one adapter = hypothetical seam"), we deliberately do not introduce a store interface yet. Tests fake the store with duck typing, and the interface is formalized only when a second adapter (e.g. in-memory) actually earns it.
