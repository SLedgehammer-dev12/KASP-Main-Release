from release_metadata import (
    APP_VERSION,
    LOCAL_BUILD_SCRIPT,
    LOCAL_SPEC_FILENAME,
    RELEASE_BUILD_SCRIPT,
    RELEASE_EXE_NAME,
    RELEASE_MAC_APP_NAME,
    RELEASE_MAC_DMG_NAME,
    RELEASE_MAC_SPEC_FILENAME,
    RELEASE_SPEC_FILENAME,
    RELEASE_TAG,
    RELEASE_VERSION,
)


def test_release_metadata_splits_source_and_release_versions():
    assert APP_VERSION == RELEASE_VERSION
    assert RELEASE_TAG == f"v{RELEASE_VERSION}"


def test_release_filenames_use_current_release_version_without_legacy_v462_tokens():
    for value in (RELEASE_SPEC_FILENAME, RELEASE_BUILD_SCRIPT, RELEASE_EXE_NAME):
        assert RELEASE_TAG in value
        assert "v462" not in value.lower()
        assert "4.6.2" not in value


def test_mac_release_artifacts_exist():
    for value in (RELEASE_MAC_APP_NAME, RELEASE_MAC_DMG_NAME, RELEASE_MAC_SPEC_FILENAME):
        assert RELEASE_TAG in value


def test_local_build_filenames_are_generic_and_no_longer_use_legacy_source_version_tokens():
    assert LOCAL_SPEC_FILENAME == "KASP_release_local.spec"
    assert LOCAL_BUILD_SCRIPT == "build_release_local.bat"


def test_release_specs_include_matplotlib_qt_backend():
    for path in (RELEASE_SPEC_FILENAME, LOCAL_SPEC_FILENAME):
        content = open(path, encoding="utf-8").read()
        assert "matplotlib.backends.backend_qt5agg" in content
