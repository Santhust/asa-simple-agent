import pytest
from asa.trace import clear_trace, reset_session

@pytest.fixture(autouse=True)
def clean_trace_before_and_after():
    """Reset trace state before and after each test.

    History (M7.3, caught by the real-letter tests): this fixture once called
    only reset_session(), which clears the in-memory IT counter — not the FILE.
    Events from earlier tests survived, violating the isolation contract.
    clear_trace() really unlinks the file (and the counter).
    """
    clear_trace()
    reset_session()
    yield
    clear_trace()
    reset_session()