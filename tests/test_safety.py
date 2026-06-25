from app.safety.handoff import should_force_handoff


def test_sensitive_terms_force_handoff():
    assert should_force_handoff("I think I have cancer")
    assert should_force_handoff("having chest pain since morning")
    assert should_force_handoff("عندي ورم")  # Arabic: "I have a tumour"


def test_routine_complaints_do_not_force_handoff():
    assert not should_force_handoff("my finger hurts")
    assert not should_force_handoff("I'd like a dermatology appointment")
    assert not should_force_handoff("where do I park")
