import os
import unittest
from unittest.mock import Mock, patch

from microsoft.sharepoint.utils import upload_image


class TestSharePointUtils(unittest.TestCase):
    @patch("microsoft.sharepoint.utils.ClientContext")
    @patch("microsoft.sharepoint.utils.ClientCredential")
    def test_upload_image_success_with_client_secret(
        self, mock_client_credential: Mock, mock_client_context: Mock
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_CLIENT_ID": "client-id",
                "SHAREPOINT_CLIENT_SECRET": "client-secret",
                "SHAREPOINT_SITE_URL": "https://tenant.sharepoint.com/sites/example",
                "SHAREPOINT_DIRECTORY": "absences",
                "SHAREPOINT_TENANT_ID": "",
                "SHAREPOINT_CERT_FINGERPRINT": "",
                "SHAREPOINT_PRIVATE_KEY": "",
            },
            clear=False,
        ):
            mock_ctx = Mock()
            mock_client_context.return_value.with_credentials.return_value = mock_ctx
            mock_uploaded_file = Mock(
                properties={
                    "ServerRelativeUrl": "/sites/example/Shared Documents/absences/chart.png"
                }
            )
            mock_folder = mock_ctx.web.get_folder_by_server_relative_url.return_value
            mock_folder.files.upload.return_value.execute_query.return_value = (
                mock_uploaded_file
            )

            result = upload_image(b"fake-image-bytes", "chart.png")

            mock_client_credential.assert_called_once_with("client-id", "client-secret")
            mock_client_context.assert_called_once_with(
                "https://tenant.sharepoint.com/sites/example"
            )
            mock_client_context.return_value.with_credentials.assert_called_once()
            mock_ctx.web.get_folder_by_server_relative_url.assert_called_once_with(
                "Shared Documents/absences"
            )
            self.assertEqual(
                result,
                "https://tenant.sharepoint.com/sites/example/Shared Documents/absences/chart.png",
            )

    @patch("microsoft.sharepoint.utils.ClientContext")
    @patch("microsoft.sharepoint.utils.ClientCredential")
    def test_upload_image_success_with_certificate(
        self, mock_client_credential: Mock, mock_client_context: Mock
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_CLIENT_ID": "client-id",
                "SHAREPOINT_CLIENT_SECRET": "",
                "SHAREPOINT_SITE_URL": "https://tenant.sharepoint.com/sites/example",
                "SHAREPOINT_DIRECTORY": "absences",
                "SHAREPOINT_TENANT_ID": "tenant-id",
                "SHAREPOINT_CERT_FINGERPRINT": "ABC123",
                "SHAREPOINT_PRIVATE_KEY": "key.pem",
            },
            clear=False,
        ):
            mock_ctx = Mock()
            mock_client_context.return_value.with_client_certificate.return_value = (
                mock_ctx
            )
            mock_uploaded_file = Mock(
                properties={
                    "ServerRelativeUrl": "/sites/example/Shared Documents/absences/chart.png"
                }
            )
            mock_folder = mock_ctx.web.get_folder_by_server_relative_url.return_value
            mock_folder.files.upload.return_value.execute_query.return_value = (
                mock_uploaded_file
            )

            result = upload_image(b"fake-image-bytes", "chart.png")

            mock_client_credential.assert_not_called()
            mock_client_context.return_value.with_client_certificate.assert_called_once_with(
                tenant="tenant-id",
                client_id="client-id",
                thumbprint="ABC123",
                cert_path="key.pem",
            )
            self.assertIn("https://tenant.sharepoint.com/sites/example/", result)

    def test_upload_image_missing_required_base_env_raises(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_CLIENT_ID": "",
                "SHAREPOINT_SITE_URL": "https://tenant.sharepoint.com/sites/example",
                "SHAREPOINT_DIRECTORY": "absences",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(
                ValueError, "SharePoint environment variables are not fully configured"
            ):
                upload_image(b"fake-image-bytes", "chart.png")

    def test_upload_image_missing_secret_in_secret_mode_raises(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_CLIENT_ID": "client-id",
                "SHAREPOINT_CLIENT_SECRET": "",
                "SHAREPOINT_SITE_URL": "https://tenant.sharepoint.com/sites/example",
                "SHAREPOINT_DIRECTORY": "absences",
                "SHAREPOINT_TENANT_ID": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Client-secret SharePoint auth requires SHAREPOINT_CLIENT_SECRET",
            ):
                upload_image(b"fake-image-bytes", "chart.png")

    def test_upload_image_missing_cert_fields_in_cert_mode_raises(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_CLIENT_ID": "client-id",
                "SHAREPOINT_CLIENT_SECRET": "",
                "SHAREPOINT_SITE_URL": "https://tenant.sharepoint.com/sites/example",
                "SHAREPOINT_DIRECTORY": "absences",
                "SHAREPOINT_TENANT_ID": "tenant-id",
                "SHAREPOINT_CERT_FINGERPRINT": "",
                "SHAREPOINT_PRIVATE_KEY": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(
                ValueError, "Certificate-based SharePoint auth requires"
            ):
                upload_image(b"fake-image-bytes", "chart.png")

    @patch("microsoft.sharepoint.utils.ClientContext")
    @patch("microsoft.sharepoint.utils.ClientCredential")
    def test_upload_image_raises_when_server_relative_url_missing(
        self, mock_client_credential: Mock, mock_client_context: Mock
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_CLIENT_ID": "client-id",
                "SHAREPOINT_CLIENT_SECRET": "client-secret",
                "SHAREPOINT_SITE_URL": "https://tenant.sharepoint.com/sites/example",
                "SHAREPOINT_DIRECTORY": "absences",
                "SHAREPOINT_TENANT_ID": "",
            },
            clear=False,
        ):
            mock_ctx = Mock()
            mock_client_context.return_value.with_credentials.return_value = mock_ctx
            mock_uploaded_file = Mock(properties={})
            mock_folder = mock_ctx.web.get_folder_by_server_relative_url.return_value
            mock_folder.files.upload.return_value.execute_query.return_value = (
                mock_uploaded_file
            )

            with self.assertRaisesRegex(
                ValueError, "Unable to resolve uploaded SharePoint file URL."
            ):
                upload_image(b"fake-image-bytes", "chart.png")


if __name__ == "__main__":
    unittest.main()
