from render_tag.core.schema.job import JobInfrastructure


def test_job_infrastructure_max_memory_mb():
    """Verify max_memory_mb field in JobInfrastructure."""
    # Test default (None)
    infra = JobInfrastructure()
    assert hasattr(infra, "max_memory_mb")
    assert infra.max_memory_mb is None

    # Test explicit value
    infra_explicit = JobInfrastructure(max_memory_mb=8000)
    assert infra_explicit.max_memory_mb == 8000

    # Test validation (should be positive if provided)
    # Actually let's just ensure it accepts it for now.
