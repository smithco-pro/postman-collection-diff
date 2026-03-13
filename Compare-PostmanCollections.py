#!/usr/bin/env python3
"""Diff two Postman collections to find added/removed requests."""

import json
import sys

def extract_requests(items, parent_path=""):
    """Recursively extract all requests as (folder_path, method, name, url)."""
    requests = []
    for item in items:
        current_path = f"{parent_path}/{item['name']}" if parent_path else item['name']
        if "item" in item:
            # It's a folder — recurse
            requests.extend(extract_requests(item["item"], current_path))
        elif "request" in item:
            req = item["request"]
            method = req.get("method", "GET")
            # Handle URL as string or object
            url = req.get("url", "")
            if isinstance(url, dict):
                url = url.get("raw", "/".join(url.get("path", [])))
            requests.append((current_path, method, url))
    return requests

def load_collection(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return extract_requests(data.get("item", []))

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} old_collection.json new_collection.json")
        sys.exit(1)

    old_file, new_file = sys.argv[1], sys.argv[2]

    old_requests = load_collection(old_file)
    new_requests = load_collection(new_file)

    # Use (folder_path, method) as the key for comparison
    old_set = set((path, method) for path, method, url in old_requests)
    new_set = set((path, method) for path, method, url in new_requests)

    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)

    # Build a lookup for URLs
    new_url_lookup = {(p, m): u for p, m, u in new_requests}
    old_url_lookup = {(p, m): u for p, m, u in old_requests}

    print(f"Old collection: {len(old_set)} requests")
    print(f"New collection: {len(new_set)} requests")
    print()

    if added:
        print(f"=== ADDED in new collection ({len(added)}) ===")
        for path, method in added:
            url = new_url_lookup.get((path, method), "")
            print(f"  + [{method}] {path}")
            print(f"          {url}")
        print()

    if removed:
        print(f"=== REMOVED from old collection ({len(removed)}) ===")
        for path, method in removed:
            url = old_url_lookup.get((path, method), "")
            print(f"  - [{method}] {path}")
            print(f"          {url}")
        print()

    if not added and not removed:
        print("No differences in request endpoints found.")

if __name__ == "__main__":
    main()
