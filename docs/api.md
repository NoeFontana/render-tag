# API Reference

This section provides comprehensive technical documentation for the `render-tag` core modules. Documentation is auto-generated from source code using `mkdocstrings`.

---

=== "Core & Schemas"

    Fundamental data structures and Pydantic models used throughout the pipeline.

    ::: render_tag.core.schema.recipe
    ::: render_tag.core.schema.job
    ::: render_tag.core.schema.subject
    ::: render_tag.core.schema.board

=== "Generation"

    Procedural mathematics and scene construction logic.

    ::: render_tag.generation.scene

=== "Orchestration"

    Worker pool management, ZMQ communication, and parallel rendering.

    ::: render_tag.orchestration.orchestrator
    ::: render_tag.orchestration.worker

=== "Data I/O"

    Dataset readers and writers for standard formats (COCO, CSV, Rich Truth).

    ::: render_tag.data_io.readers
    ::: render_tag.data_io.writers

=== "Audit"

    Dataset quality verification and telemetry analysis.

    ::: render_tag.audit.auditor

=== "Backend"

    The 3D rendering driver that runs inside the Blender environment.

    ::: render_tag.backend.engine
    ::: render_tag.backend.worker_server
