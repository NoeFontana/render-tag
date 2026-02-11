from render_tag.backend.bridge import bproc, bpy, bridge, np


def test_bridge_singleton():
    from render_tag.backend.bridge import BlenderBridge

    b1 = BlenderBridge()
    b2 = BlenderBridge()
    assert b1 is b2
    assert bridge is b1


def test_bridge_provides_mocks_in_test_env():
    # In this environment, we expect mocks
    assert bpy is not None
    assert bproc is not None

    # Verify it's a mock by checking for an attribute we know we added to mocks
    assert hasattr(bpy.context.scene, "cycles")
    assert hasattr(bproc, "init")


def test_bridge_provides_numpy():
    assert np is not None
    assert hasattr(np, "array")


def test_bridge_injection():
    class FakeBproc:
        pass

    class FakeBpy:
        pass

    bridge.inject_mocks(FakeBproc(), FakeBpy())

    # Note: the top-level 'bpy' and 'bproc' in bridge.py are already bound
    # so we check bridge.bpy/bridge.bproc
    assert isinstance(bridge.bproc, FakeBproc)
    assert isinstance(bridge.bpy, FakeBpy)

    # Reset for other tests if needed, but since it's a singleton it might affect them.
    # For unit tests, we'll just re-init or accept it.
    bridge._load_dependencies()
