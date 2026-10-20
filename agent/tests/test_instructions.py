from prompts import ClinicConfig, Doctor, build_system_prompt, load_clinic_config


def test_prompt_uses_clinic_config() -> None:
    config = ClinicConfig(
        name="Test Clinic",
        doctors=(
            Doctor(
                name="Dr. Asha Rao",
                specialty="General Physician",
                days="Mon, Wed, Fri",
                hours="10:00-13:00",
            ),
        ),
        timings={"Monday": "09:00-18:00", "Sunday": "Closed"},
        timezone="Asia/Kolkata",
        address="1 Test Road",
        phone="+91 98765 43210",
        fees="INR 500",
        emergency_number="112",
    )

    prompt = build_system_prompt(config)

    assert "Test Clinic" in prompt
    assert "Dr. Asha Rao" in prompt
    assert "Monday: 09:00-18:00" in prompt
    assert "Sunday: Closed" in prompt
    assert "1 Test Road" in prompt
    assert "INR 500" in prompt
    assert "112" in prompt
    assert "AI" in prompt
    assert "Hindi" in prompt
    assert "English" in prompt
    assert "Never give medical advice" in prompt
    assert "read back" in prompt.lower()


def test_prompt_does_not_invent_missing_config() -> None:
    prompt = build_system_prompt(ClinicConfig(name="Test Clinic"))

    assert "Do not invent doctor names" in prompt
    assert "Do not invent them" in prompt


def test_load_clinic_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CLINIC_NAME", "Env Clinic")
    monkeypatch.setenv("CLINIC_DOCTORS", '[{"name":"Dr. B","specialty":"ENT"}]')
    monkeypatch.setenv("CLINIC_TIMINGS", '{"Tuesday":"10:00-17:00"}')

    config = load_clinic_config()

    assert config.name == "Env Clinic"
    assert config.doctors[0].name == "Dr. B"
    assert config.doctors[0].specialty == "ENT"
    assert config.timings == {"Tuesday": "10:00-17:00"}
