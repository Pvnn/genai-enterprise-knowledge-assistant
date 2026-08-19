"""Object storage utility for Neon Object Storage.

Owner: P1
Provides functions to upload and download document markdown contents securely
from the configured Neon Object Storage S3-compatible bucket.
"""

import asyncio
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_s3_client():
    settings = get_settings()
    if not all([settings.aws_endpoint_url_s3, settings.aws_access_key_id, settings.aws_secret_access_key]):
        return None
    
    return boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url_s3,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region or "us-east-2"
    )

def _get_bucket_name(client) -> Optional[str]:
    try:
        response = client.list_buckets()
        buckets = response.get("Buckets", [])
        if buckets:
            return buckets[0]["Name"]
        return None
    except Exception as e:
        logger.error("Failed to list buckets: %s", e)
        return None


def _upload_markdown_sync(object_key: str, content: str) -> None:
    client = _get_s3_client()
    if not client:
        logger.warning("S3 credentials not configured. Skipping upload for %s", object_key)
        return

    bucket_name = _get_bucket_name(client)
    if not bucket_name:
        logger.warning("No S3 bucket found. Skipping upload for %s", object_key)
        return

    try:
        client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=content.encode("utf-8"),
            ContentType="text/markdown"
        )
        logger.info("Successfully uploaded %s to Neon Object Storage.", object_key)
    except ClientError as e:
        logger.error("Failed to upload %s to S3: %s", object_key, e)
        raise


def _get_markdown_sync(object_key: str) -> Optional[str]:
    client = _get_s3_client()
    if not client:
        logger.warning("S3 credentials not configured. Cannot download %s", object_key)
        return None
        
    bucket_name = _get_bucket_name(client)
    if not bucket_name:
        logger.warning("No S3 bucket found. Cannot download %s", object_key)
        return None

    try:
        response = client.get_object(
            Bucket=bucket_name,
            Key=object_key
        )
        return response['Body'].read().decode("utf-8")
    except ClientError as e:
        logger.error("Failed to download %s from S3: %s", object_key, e)
        raise


async def upload_markdown(object_key: str, content: str) -> None:
    """Uploads markdown text to Neon Object Storage asynchronously.

    Args:
        object_key: The S3 object key where the markdown will be stored.
        content: The plaintext markdown content to upload.

    Raises:
        ClientError: If the upload operation to S3 fails.
    """
    await asyncio.to_thread(_upload_markdown_sync, object_key, content)


async def get_markdown(object_key: str) -> Optional[str]:
    """Downloads markdown text from Neon Object Storage asynchronously.

    Args:
        object_key: The S3 object key of the markdown file.

    Returns:
        Optional[str]: The markdown content as a string, or None if the
        credentials or bucket are not configured.

    Raises:
        ClientError: If the download operation from S3 fails.
    """
    return await asyncio.to_thread(_get_markdown_sync, object_key)
