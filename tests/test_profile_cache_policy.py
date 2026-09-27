from xcel_meter.addon_runtime import (
    _should_invalidate_meter_profile,
)
from xcel_meter.http import (
    MeterHttpError,
    _is_retryable_transport_error,
)


def test_404_invalidates_cached_meter_profile():
    exc = MeterHttpError(
        "not found",
        kind="http",
        status=404,
        path="/upt/1/mr/1/r",
    )

    assert exc.invalidates_profile is True
    assert _should_invalidate_meter_profile(exc) is True


def test_410_invalidates_cached_meter_profile():
    exc = MeterHttpError(
        "gone",
        kind="http",
        status=410,
        path="/upt/1/mr/1/r",
    )

    assert _should_invalidate_meter_profile(exc) is True


def test_server_error_keeps_cached_meter_profile():
    exc = MeterHttpError(
        "server error",
        kind="http",
        status=500,
        path="/upt/1/mr/1/r",
    )

    assert exc.invalidates_profile is False
    assert _should_invalidate_meter_profile(exc) is False


def test_transport_failure_keeps_cached_meter_profile():
    exc = MeterHttpError(
        "timed out",
        kind="transport",
        path="/upt/1/mr/1/r",
    )

    assert exc.invalidates_profile is False
    assert _should_invalidate_meter_profile(exc) is False


def test_timeout_is_retryable_transport_failure():
    assert _is_retryable_transport_error(
        TimeoutError("timed out")
    ) is True


def test_connection_reset_is_retryable_transport_failure():
    assert _is_retryable_transport_error(
        ConnectionResetError("reset")
    ) is True
