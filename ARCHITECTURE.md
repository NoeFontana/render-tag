# System Architecture

The technical documentation for `render-tag`'s architecture has moved to the central documentation site:

👉 **[Architecture Guide](docs/architecture.md)**

### Key Highlights
*   **Host-Backend Decoupling**: Pure Python generation logic paired with optimized Blender rendering.
*   **ZMQ Hot Loop**: Persistent workers to minimize overhead.
*   **Orientation Contract**: Strict geometric association between 3D assets and 2D annotations.
