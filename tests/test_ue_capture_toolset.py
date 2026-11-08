import ue_capture_toolset


def test_version_and_exports() -> None:
    assert ue_capture_toolset.__version__ == "0.1.0"
    for name in ue_capture_toolset.__all__:
        assert hasattr(ue_capture_toolset, name)
