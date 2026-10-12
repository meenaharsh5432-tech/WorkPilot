from unittest.mock import Mock

from sqlalchemy.exc import OperationalError

from app.agent.executor import run_with_retry


def test_read_retry_succeeds_after_one_failure():
    operation = Mock(
        side_effect=[
            OperationalError(
                "SELECT invoice",
                {},
                Exception("temporary database failure")
            ),
            {"invoice_id": 5}
        ]
    )

    result = run_with_retry(
        operation=operation,
        tool_name="get_invoice",
        max_attempts=2
    )

    assert result == {"invoice_id": 5}
    assert operation.call_count == 2


def test_read_retry_stops_after_limit():
    operation = Mock(
        side_effect=OperationalError(
            "SELECT invoice",
            {},
            Exception("database unavailable")
        )
    )

    try:
        run_with_retry(
            operation=operation,
            tool_name="get_invoice",
            max_attempts=2
        )
        assert False, "Expected database error"
    except OperationalError:
        pass

    assert operation.call_count == 2


def test_write_operations_are_not_retried():
    operation = Mock(
        side_effect=OperationalError(
            "INSERT invoice",
            {},
            Exception("database unavailable")
        )
    )

    try:
        run_with_retry(
            operation=operation,
            tool_name="save_invoice",
            max_attempts=2
        )
        assert False, "Expected database error"
    except OperationalError:
        pass

    assert operation.call_count == 1