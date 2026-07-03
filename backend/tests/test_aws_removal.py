"""Removal-guard test for AWS Secrets Manager / boto3 cleanup (PROD-04-05).

Both tests MUST FAIL before Task 2 (boto3 still installed, config fields still
present). After Task 2 removes the dep and config fields, both MUST PASS.
"""

import pytest


def test_boto3_not_installed():
    with pytest.raises(ModuleNotFoundError):
        import boto3  # noqa: F401


def test_settings_has_no_aws_fields():
    from app.config import Settings

    field_names = set(Settings.model_fields.keys())  # pydantic v2
    assert "aws_region" not in field_names
    assert "secrets_manager_prefix" not in field_names
