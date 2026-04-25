import os
from io import BytesIO
from urllib.parse import urlparse

from dotenv import load_dotenv
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

from logger.utils import get_logger

load_dotenv()
logger = get_logger(__name__)


def upload_image(image_content: bytes, file_name: str) -> str:
    logger.info("Uploading image to SharePoint.")
    try:
        client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        site_url = os.getenv("SHAREPOINT_SITE_URL")
        target_directory = f"Shared Documents/{os.getenv('SHAREPOINT_DIRECTORY')}"
        tenant_id = os.getenv("SHAREPOINT_TENANT_ID")

        cert_fingerprint = os.getenv("SHAREPOINT_CERT_FINGERPRINT")
        private_key = os.getenv("SHAREPOINT_PRIVATE_KEY")

        if not client_id or not site_url or not target_directory:
            raise ValueError(
                "SharePoint environment variables are not fully configured. Required: "
                "SHAREPOINT_CLIENT_ID, SHAREPOINT_SITE_URL, SHAREPOINT_DIRECTORY."
            )
        if tenant_id:
            if not cert_fingerprint or not private_key:
                raise ValueError(
                    "Certificate-based SharePoint auth requires "
                    "SHAREPOINT_TENANT_ID, SHAREPOINT_CERT_FINGERPRINT, and "
                    "SHAREPOINT_PRIVATE_KEY."
                )
        elif not client_secret:
            raise ValueError(
                "Client-secret SharePoint auth requires SHAREPOINT_CLIENT_SECRET "
                "when SHAREPOINT_TENANT_ID is not provided."
            )

        if not tenant_id:
            credentials = ClientCredential(client_id, client_secret)
            ctx = ClientContext(site_url).with_credentials(credentials)
        else:
            cert_settings = {
                "tenant": os.getenv("SHAREPOINT_TENANT_ID"),
                "client_id": os.getenv("SHAREPOINT_CLIENT_ID"),
                "thumbprint": os.getenv("SHAREPOINT_CERT_FINGERPRINT"),
                "cert_path": os.getenv("SHAREPOINT_PRIVATE_KEY"),
            }
            ctx = ClientContext(
                os.getenv("SHAREPOINT_SITE_URL")
            ).with_client_certificate(**cert_settings)

        target_folder = ctx.web.get_folder_by_server_relative_url(target_directory)
        with BytesIO(image_content) as file_stream:
            uploaded_file = target_folder.files.upload(
                file_stream, file_name
            ).execute_query()

        server_relative_url = uploaded_file.properties.get("ServerRelativeUrl")
        if not server_relative_url:
            raise ValueError("Unable to resolve uploaded SharePoint file URL.")

        parsed_site_url = urlparse(site_url)
        absolute_url = (
            f"{parsed_site_url.scheme}://{parsed_site_url.netloc}{server_relative_url}"
        )
        logger.info(f"File '{file_name}' uploaded successfully to: {absolute_url}")
        return absolute_url
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise
