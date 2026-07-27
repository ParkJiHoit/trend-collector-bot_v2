import time

import requests

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _request(method, path, token, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{path}"

    response = requests.request(method, url, headers=headers, timeout=10, **kwargs)
    if response.status_code == 429:
        time.sleep(float(response.headers.get("Retry-After", 1)))
        response = requests.request(method, url, headers=headers, timeout=10, **kwargs)

    if not response.ok:
        print(f"⚠️ Notion API error {response.status_code}: {response.text}")
    response.raise_for_status()
    return response.json()


def query_database(database_id, token):
    return _request("POST", f"/databases/{database_id}/query", token)


def create_page(database_id, properties, token, children=None):
    body = {"parent": {"database_id": database_id}, "properties": properties}
    if children:
        body["children"] = children
    return _request("POST", "/pages", token, json=body)
