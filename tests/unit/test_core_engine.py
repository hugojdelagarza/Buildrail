from buildrail.core import CoreEngine, Result


def test_run_returns_a_successful_placeholder_result() -> None:
    engine = CoreEngine()

    result = engine.run()

    assert isinstance(result, Result)
    assert result.success is True
    assert result.message == "Buildrail initialized."
