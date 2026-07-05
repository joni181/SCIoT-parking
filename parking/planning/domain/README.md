# PDDL domain

`domain.pddl` defines admission assignment, entry authorization, spot indication,
parking, retrieval, and exit authorization over cars, spots, and buffers. Runtime
problems represent one sensor-bounded phase; physical confirmation triggers the
next problem so plans cannot run ahead of the real parking lot.
