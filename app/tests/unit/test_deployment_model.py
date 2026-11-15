# app/tests/unit/test_deployment_model.py
"""Pure-logic tests for the tenant deployment topology (no DB needed)."""
import pytest

from app.core.enums import DeploymentModel
from app.schemas.tenant_schemas import (
    VALID_DEPLOYMENT_MODELS,
    normalize_deployment_model,
    deployment_mode_for_model,
    TenantRegistrationSchema,
)


class TestDeploymentEnum:
    def test_three_canonical_values(self):
        assert {m.value for m in DeploymentModel} == {
            "ON_PREMISE", "CLOUD_DEDICATED", "CLOUD_PLATFORM"}
        assert VALID_DEPLOYMENT_MODELS == {
            "ON_PREMISE", "CLOUD_DEDICATED", "CLOUD_PLATFORM"}


class TestNormalizeDeploymentModel:
    @pytest.mark.parametrize("raw,expected", [
        ("ON_PREMISE", "ON_PREMISE"),
        ("on-premise", "ON_PREMISE"),
        ("onprem", "ON_PREMISE"),
        ("local", "ON_PREMISE"),
        ("CLOUD_DEDICATED", "CLOUD_DEDICATED"),
        ("dedicated", "CLOUD_DEDICATED"),
        ("cloud-dedicated", "CLOUD_DEDICATED"),
        ("CLOUD_PLATFORM", "CLOUD_PLATFORM"),
        ("platform", "CLOUD_PLATFORM"),
        ("cloud", "CLOUD_PLATFORM"),
        ("saas", "CLOUD_PLATFORM"),
    ])
    def test_synonyms_map_to_canonical(self, raw, expected):
        assert normalize_deployment_model(raw) == expected

    def test_blank_and_unknown_default_to_platform(self):
        assert normalize_deployment_model(None) == "CLOUD_PLATFORM"
        assert normalize_deployment_model("") == "CLOUD_PLATFORM"
        assert normalize_deployment_model("something-else") == "CLOUD_PLATFORM"

    def test_case_insensitive(self):
        assert normalize_deployment_model("Dedicated") == "CLOUD_DEDICATED"
        assert normalize_deployment_model("  On-Premise ") == "ON_PREMISE"


class TestDeploymentModeDerivation:
    def test_on_premise_is_onprem(self):
        assert deployment_mode_for_model("ON_PREMISE") == "onprem"

    def test_cloud_variants_are_cloud(self):
        assert deployment_mode_for_model("CLOUD_DEDICATED") == "cloud"
        assert deployment_mode_for_model("CLOUD_PLATFORM") == "cloud"


def _reg(**overrides):
    base = dict(
        tenant_name="Test Hospital",
        tenant_code="TESTHOSP",
        domain_url="https://testhosp.carepointhms.com",
        plan_code="STANDARD",
        admin_email="admin@test.com",
        admin_username="admin.user",
        admin_password="supersecret",
        admin_first_name="Ada",
        admin_last_name="Admin",
    )
    base.update(overrides)
    return TenantRegistrationSchema(**base)


class TestRegistrationSchemaDeploymentField:
    def test_defaults_to_platform(self):
        assert _reg().deployment_model == "CLOUD_PLATFORM"

    def test_normalizes_supplied_value(self):
        assert _reg(deployment_model="dedicated").deployment_model == "CLOUD_DEDICATED"
        assert _reg(deployment_model="on-premise").deployment_model == "ON_PREMISE"

    def test_unknown_value_falls_back_to_platform(self):
        assert _reg(deployment_model="nonsense").deployment_model == "CLOUD_PLATFORM"
