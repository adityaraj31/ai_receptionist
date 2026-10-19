from receptionist_agent import TTS_LANGUAGE, build_instructions


def test_instructions_disclose_ai_and_language_handling() -> None:
    instructions = build_instructions("Test Clinic")

    assert "Test Clinic" in instructions
    assert "AI" in instructions
    assert "Hindi" in instructions
    assert "English" in instructions
    assert "Never give medical advice" in instructions


def test_tts_language_has_a_default() -> None:
    assert TTS_LANGUAGE
