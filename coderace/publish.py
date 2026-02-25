"""Publish HTML to here.now hosting service."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    """Result from publishing a file."""

    url: str
    publish_id: str
    expires: bool


class PublishError(Exception):
    """Error during publish operation."""


HERENOW_API_BASE = "https://here.now/api/v1"


def publish_html(
    html_content: str,
    *,
    api_key: str | None = None,
    api_base: str | None = None,
) -> PublishResult:
    """Publish HTML content to here.now.

    3-step flow:
    1. POST /publish — create upload, get upload URL
    2. PUT file to upload URL
    3. POST /publish/{id}/finalize — finalize, get public URL

    Args:
        html_content: The HTML string to publish.
        api_key: Optional API key for persistent publish. Falls back to
                 HERENOW_API_KEY env var. If not provided, anonymous
                 publish with 24h expiry.
        api_base: Override API base URL (for testing).

    Returns:
        PublishResult with the public URL.

    Raises:
        PublishError: If any step of the publish flow fails.
    """
    base = api_base or HERENOW_API_BASE
    key = api_key or os.environ.get("HERENOW_API_KEY")

    # Step 1: Create upload
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    create_body = json.dumps({
        "filename": "dashboard.html",
        "content_type": "text/html",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/publish",
        data=create_body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            create_data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise PublishError(f"Failed to create upload: {exc}") from exc

    upload_url = create_data.get("upload_url")
    publish_id = create_data.get("id")

    if not upload_url or not publish_id:
        raise PublishError(f"Invalid response from create: {create_data}")

    # Step 2: Upload the file
    put_req = urllib.request.Request(
        upload_url,
        data=html_content.encode("utf-8"),
        headers={"Content-Type": "text/html"},
        method="PUT",
    )

    try:
        with urllib.request.urlopen(put_req, timeout=60) as resp:
            pass
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise PublishError(f"Failed to upload file: {exc}") from exc

    # Step 3: Finalize
    finalize_headers = {"Content-Type": "application/json"}
    if key:
        finalize_headers["Authorization"] = f"Bearer {key}"

    finalize_req = urllib.request.Request(
        f"{base}/publish/{publish_id}/finalize",
        data=b"{}",
        headers=finalize_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(finalize_req, timeout=30) as resp:
            finalize_data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise PublishError(f"Failed to finalize publish: {exc}") from exc

    public_url = finalize_data.get("url")
    if not public_url:
        raise PublishError(f"No URL in finalize response: {finalize_data}")

    return PublishResult(
        url=public_url,
        publish_id=str(publish_id),
        expires=key is None,
    )
