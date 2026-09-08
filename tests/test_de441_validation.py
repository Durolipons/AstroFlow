"""Tests for DE441 kernel validation helpers."""

from astronomy.validation import validate_de441_kernel_file


class _FakeSegment:
    def __init__(self, target, start_jd, end_jd):
        self.target = target
        self.start_jd = start_jd
        self.end_jd = end_jd


class _FakeKernel:
    def __init__(self, segments):
        self.segments = segments

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_validate_de441_kernel_reports_missing_path(monkeypatch):
    monkeypatch.delenv("ASTROFLOW_DE441_KERNEL", raising=False)
    report = validate_de441_kernel_file()
    assert report.valid is False
    assert "not configured" in report.messages[0]


def test_validate_de441_kernel_reports_valid_fake_kernel(monkeypatch):
    path = r"C:\kernels\de441.bsp"
    segments = [
        _FakeSegment(10, 2400000.5, 2600000.5),
        _FakeSegment(199, 2400000.5, 2600000.5),
        _FakeSegment(299, 2400000.5, 2600000.5),
        _FakeSegment(301, 2400000.5, 2600000.5),
        _FakeSegment(399, 2400000.5, 2600000.5),
        _FakeSegment(499, 2400000.5, 2600000.5),
        _FakeSegment(599, 2400000.5, 2600000.5),
        _FakeSegment(699, 2400000.5, 2600000.5),
        _FakeSegment(799, 2400000.5, 2600000.5),
        _FakeSegment(899, 2400000.5, 2600000.5),
        _FakeSegment(999, 2400000.5, 2600000.5),
    ]
    monkeypatch.setattr("astronomy.validation.os.path.isfile", lambda value: value == path)
    monkeypatch.setattr(
        "astronomy.validation._open_validation_kernel",
        lambda resolved: _FakeKernel(segments),
    )

    report = validate_de441_kernel_file(path)

    assert report.valid is True
    assert report.segment_count == len(segments)
    assert report.coverage_start_jd == 2400000.5
    assert report.coverage_end_jd == 2600000.5
    assert report.missing_targets == ()
