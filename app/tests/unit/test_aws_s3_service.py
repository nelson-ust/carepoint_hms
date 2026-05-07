# app/tests/unit/test_aws_s3_service.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from botocore.exceptions import ClientError
from app.services.aws_s3_service import S3Service

@pytest.fixture
def service():
    """
    NB: this fixture must ``yield`` (not ``return``) the service so the
    ``patch`` context managers stay active for the duration of the
    test body. Returning would tear the patches down before the test
    runs — the live ``settings`` would then leak in, and assertions
    that depend on the patched values (e.g. ``is_development``)
    would flip with whatever ``CAREPOINT_HMS_ENVIRONMENT`` happens
    to be set to in the runtime/test environment.
    """
    with patch("boto3.client"):
        with patch("app.services.aws_s3_service.settings") as mock_settings:
            mock_settings.AWS_ACCESS_KEY_ID.get_secret_value.return_value = "key"
            mock_settings.AWS_SECRET_ACCESS_KEY.get_secret_value.return_value = "secret"
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            mock_settings.S3_ENABLED = True
            mock_settings.is_development = True

            yield S3Service()

class TestS3Service:

    def test_create_tenant_bucket_success(self, service):
        service.s3_client.create_bucket = MagicMock()
        
        bucket_name = service.create_tenant_bucket("test-tenant")
        
        assert "carepoint-hms-test-tenant-dev" in bucket_name
        service.s3_client.create_bucket.assert_called_once_with(Bucket=bucket_name)

    def test_create_tenant_bucket_failure(self, service):
        service.s3_client.create_bucket = MagicMock(side_effect=ClientError({"Error": {"Code": "500", "Message": "Err"}}, "create_bucket"))
        
        bucket_name = service.create_tenant_bucket("test-tenant")
        assert bucket_name is None

    def test_upload_file_success(self, service):
        mock_file = MagicMock()
        mock_file.file = MagicMock()
        mock_file.content_type = "image/png"
        service.s3_client.upload_fileobj = MagicMock()
        
        url = service.upload_file("my-bucket", mock_file, "path/to/file.png")
        
        assert "my-bucket.s3.us-east-1.amazonaws.com/path/to/file.png" in url
        service.s3_client.upload_fileobj.assert_called_once()

    def test_generate_presigned_url_success(self, service):
        service.s3_client.generate_presigned_url = MagicMock(return_value="https://presigned-url.com")
        
        url = service.generate_presigned_url("my-bucket", "key")
        assert url == "https://presigned-url.com"
        service.s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "key"},
            ExpiresIn=3600
        )

    def test_skips_when_disabled(self, service):
        service.is_enabled = False
        assert service.create_tenant_bucket("abc") is None
        assert service.upload_file("bucket", MagicMock(), "key") is None
        assert service.generate_presigned_url("bucket", "key") is None
