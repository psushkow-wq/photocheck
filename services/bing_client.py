"""
services/bing_client.py — Microsoft Bing Visual Search API client.

API docs: https://learn.microsoft.com/en-us/bing/search-apis/bing-visual-search/overview
"""

import json
import logging
import uuid
from pathlib import Path

import requests

from config import Config
from core.models import ReverseSearchMatch

logger = logging.getLogger(__name__)

BING_VISUAL_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/images/visualsearch"


class BingClient:
    def search(self, image_path: str) -> list[ReverseSearchMatch]:
        path = Path(image_path)
        boundary = f"batch_{uuid.uuid4().hex}"

        with open(path, "rb") as f:
            image_data = f.read()

        headers = {
            "Ocp-Apim-Subscription-Key": Config.BING_SEARCH_KEY,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + image_data + f"\r\n--{boundary}--\r\n".encode()

        resp = requests.post(
            BING_VISUAL_SEARCH_URL, headers=headers, data=body,
            timeout=Config.REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        matches = []
        for tag in data.get("tags", []):
            for action in tag.get("actions", []):
                if action.get("actionType") == "PagesIncluding":
                    for item in action.get("data", {}).get("value", []):
                        matches.append(ReverseSearchMatch(
                            service="Bing Visual Search",
                            found=True,
                            url=item.get("hostPageUrl", ""),
                            page_title=item.get("name", ""),
                            thumbnail_url=item.get("thumbnailUrl", ""),
                            match_type="visual",
                        ))

        if not matches:
            matches.append(ReverseSearchMatch(service="Bing Visual Search", found=False))
        return matches
