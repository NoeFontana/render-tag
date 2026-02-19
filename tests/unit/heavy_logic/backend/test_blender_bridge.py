from render_tag.backend.bridge import bridge


def test_bridge_singleton():
    from render_tag.backend.bridge import BlenderBridge

    b1 = BlenderBridge()
    b2 = BlenderBridge()
    assert b1 is b2
    assert bridge is b1


def test_bridge_provides_mocks_in_test_env():
    # In this environment, we expect mocks
    bridge.stabilize()
    assert bridge.bpy is not None
    assert bridge.bproc is not None

    # Verify it's a mock by checking for an attribute we know we added to mocks
    assert hasattr(bridge.bpy.context.scene, "cycles")
    assert hasattr(bridge.bproc, "init")


def test_bridge_provides_numpy():
    bridge.stabilize()
    assert bridge.np is not None
    assert hasattr(bridge.np, "array")


def test_bridge_injection():
    class FakeBproc:
        pass

    class FakeBpy:
        pass

    # Stabilize with fake modules
    bridge.stabilize(bproc_module=FakeBproc(), bpy_module=FakeBpy())

    assert bridge.bproc is not None
    assert bridge.bpy is not None

    # Note: the top-level 'bpy' and 'bproc' in bridge.py are already bound
    # so we check bridge.bpy/bridge.bproc
    assert isinstance(bridge.bproc, FakeBproc)
    assert isinstance(bridge.bpy, FakeBpy)

    # Restabilize for other tests since this is a singleton
    bridge.stabilize()
