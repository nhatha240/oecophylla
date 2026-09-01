from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_local_rollout_config_keeps_v1_default_and_exposes_v2_tuning():
    env_example = _read(".env.example")
    compose = _read("compose.yaml")

    expected_defaults = {
        "PREFERENCE_SCHEMA_VERSION": "v1",
        "PREFERENCE_HALF_LIFE_HOURS": "720",
        "PREFERENCE_CHANNEL_BOUND": "10",
        "PREFERENCE_BEHAVIOR_COEFFICIENT": "0.75",
        "PREFERENCE_DECLARED_COEFFICIENT": "0.25",
        "PREFERENCE_EVIDENCE_SATURATION": "2.5",
        "PREFERENCE_BACKFILL_ON_START": "false",
        "PREFERENCE_BACKFILL_BATCH_SIZE": "500",
    }
    for name, value in expected_defaults.items():
        assert f"{name}={value}" in env_example
        assert f"{name}: ${{{name}:-{value}}}" in compose


def test_helm_rollout_config_exposes_the_same_preference_defaults():
    values = _read("charts/oecophylla/values.yaml")
    configmap = _read("charts/oecophylla/templates/configmap.yaml")

    expected_values = {
        "preferenceSchemaVersion": "v1",
        "preferenceHalfLifeHours": '"720"',
        "preferenceChannelBound": '"10"',
        "preferenceBehaviorCoefficient": '"0.75"',
        "preferenceDeclaredCoefficient": '"0.25"',
        "preferenceEvidenceSaturation": '"2.5"',
        "preferenceBackfillOnStart": '"false"',
        "preferenceBackfillBatchSize": '"500"',
    }
    for name, value in expected_values.items():
        assert f"{name}: {value}" in values
        assert f".Values.config.{name}" in configmap
