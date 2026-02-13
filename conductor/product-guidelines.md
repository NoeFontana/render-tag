# Product Guidelines

## Communication Style
- **Concise & Direct:** All technical documentation, CLI output, and internal comments must be professional and direct. Prioritize clarity and efficiency of information delivery over conversational tone.
- **Utility-Centric Voice:** The project's "voice" should be practical and task-oriented. Focus on how features solve specific user problems and help them generate high-quality datasets efficiently.

## Visual Identity & Data Clarity
- **Clinical Information Overlays:** While primary renders aim for high photorealism, all debugging and visualization tools must prioritize data clarity. Use high-contrast colors, clear labels, and minimal aesthetic embellishment for ground-truth overlays.
- **Photorealistic Priority:** For the core dataset, prioritize realistic lighting, material properties, and sensor artifacts to ensure maximum utility for training models destined for real-world deployment.
- **Structured Feedback**: Prioritize structured, machine-readable telemetry (NDJSON) over raw text logs. Use progress bars and categorized metrics to provide high-fidelity feedback during long-running tasks.

## Error Handling & Reliability
- **Resilient Batch Processing:** During large-scale generation, the system must be resilient. If a single scene or shard fails, it should be logged and skipped, allowing the rest of the batch to complete.
- **Comprehensive Reporting:** A detailed summary of successes and failures must be provided at the end of every batch run, including pointers to specific logs for failed scenes.

## Engineering Principles
- **Schema-First Development:** All internal contracts between the generator and the renderer (e.g., Scene Recipes) must be defined by strict schemas (using Pydantic). Validation must occur at every boundary.
- **Strict Logic Isolation:** Generation logic must remain pure and environment-agnostic. Dependencies like `bpy` (Blender) must be confined to backend rendering scripts and never leak into the core generation or geometry modules.
- **Component Composition:** Build features using small, single-purpose components. Favor composition over deep inheritance to maintain a flexible and testable codebase.
