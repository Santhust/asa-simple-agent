import pytest
from asa.trace import reset_session

@pytest.fixture(autouse=True)
def clean_trace_before_and_after():
    """Reset trace state before and after each test."""
    reset_session()
    yield
    reset_session()