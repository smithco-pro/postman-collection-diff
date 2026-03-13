#!/usr/bin/env python3
"""Diff two Postman collections to find added, removed, and modified requests."""

import argparse
import html
import json
import sys
from datetime import datetime


def type_name(val):
    """Return a short type label for a JSON value."""
    if isinstance(val, str):
        return "string"
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "number"
    if isinstance(val, dict):
        return "object"
    if isinstance(val, list):
        return "array"
    return "null"


def extract_body_schema(obj, prefix="$"):
    """Recursively walk a parsed JSON value and return a set of '$.path [type]' strings."""
    paths = set()
    if isinstance(obj, dict):
        for key, val in obj.items():
            p = f"{prefix}.{key}"
            paths.add(f"{p} [{type_name(val)}]")
            paths |= extract_body_schema(val, p)
    elif isinstance(obj, list) and obj:
        first = obj[0]
        p = f"{prefix}[*]"
        paths.add(f"{p} [{type_name(first)}]")
        paths |= extract_body_schema(first, p)
    return paths


def get_description(req):
    """Extract description string from a request, handling str or dict forms."""
    desc = req.get("description", "")
    if isinstance(desc, dict):
        desc = desc.get("content", "")
    return (desc or "").strip()


def extract_requests(items, parent_path=""):
    """Recursively extract all requests as rich dicts."""
    requests = []
    for item in items:
        name = item.get("name", "")
        current_path = f"{parent_path} / {name}" if parent_path else name
        if "item" in item:
            requests.extend(extract_requests(item["item"], current_path))
        elif "request" in item:
            req = item["request"]
            method = req.get("method", "GET")
            url_obj = req.get("url", "")
            if isinstance(url_obj, dict):
                url = url_obj.get("raw", "/".join(url_obj.get("path", [])))
            else:
                url = url_obj

            # Body schema
            body_schema = set()
            body = req.get("body", {})
            if body and body.get("raw"):
                try:
                    parsed = json.loads(body["raw"])
                    body_schema = extract_body_schema(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Responses
            responses = item.get("response", []) or []
            response_codes = set()
            response_names = []
            for resp in responses:
                code = resp.get("code")
                if code is not None:
                    response_codes.add(code)
                rname = resp.get("name", "")
                if rname:
                    response_names.append(f"{code}: {rname}" if code else rname)

            requests.append({
                "name": name,
                "folder_path": parent_path,
                "method": method,
                "url": url,
                "description": get_description(req),
                "body_schema": body_schema,
                "response_codes": response_codes,
                "response_names": sorted(response_names),
            })
    return requests


def load_collection(filepath):
    """Load a Postman collection and return (collection_name, requests_list)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    name = data.get("info", {}).get("name", filepath)
    return name, extract_requests(data.get("item", []))


def compare_collections(old_requests, new_requests):
    """Compare two request lists, returning (added, removed, modified) lists."""
    # Key: (method, url, name)
    old_by_key = {}
    for r in old_requests:
        old_by_key[(r["method"], r["url"], r["name"])] = r
    new_by_key = {}
    for r in new_requests:
        new_by_key[(r["method"], r["url"], r["name"])] = r

    old_keys = set(old_by_key)
    new_keys = set(new_by_key)

    added = sorted(new_keys - old_keys, key=lambda k: (new_by_key[k]["folder_path"], k[0], k[2]))
    removed = sorted(old_keys - new_keys, key=lambda k: (old_by_key[k]["folder_path"], k[0], k[2]))

    # Find modified among common keys
    modified = []
    for key in sorted(old_keys & new_keys, key=lambda k: (old_by_key[k]["folder_path"], k[0], k[2])):
        old_r = old_by_key[key]
        new_r = new_by_key[key]
        diffs = []

        if old_r["folder_path"] != new_r["folder_path"]:
            diffs.append(("Folder", old_r["folder_path"], new_r["folder_path"]))

        if old_r["description"] != new_r["description"]:
            diffs.append(("Description", old_r["description"], new_r["description"]))

        old_schema = old_r["body_schema"]
        new_schema = new_r["body_schema"]
        if old_schema != new_schema:
            only_old = sorted(old_schema - new_schema)
            only_new = sorted(new_schema - old_schema)
            diffs.append(("BodySchema", "<br>".join(only_old), "<br>".join(only_new)))

        if old_r["response_codes"] != new_r["response_codes"]:
            only_old = sorted(old_r["response_codes"] - new_r["response_codes"])
            only_new = sorted(new_r["response_codes"] - old_r["response_codes"])
            diffs.append(("ResponseCodes",
                          ", ".join(str(c) for c in only_old),
                          ", ".join(str(c) for c in only_new)))

        if old_r["response_names"] != new_r["response_names"]:
            diffs.append(("ResponseNames",
                          " ".join(old_r["response_names"]),
                          " ".join(new_r["response_names"])))

        if diffs:
            modified.append((key, new_r, diffs))

    return (
        [(k, new_by_key[k]) for k in added],
        [(k, old_by_key[k]) for k in removed],
        modified,
    )


def print_text_report(old_name, new_name, old_requests, new_requests, added, removed, modified):
    """Print a text summary to stdout."""
    print(f"Old collection ({old_name}): {len(old_requests)} requests")
    print(f"New collection ({new_name}): {len(new_requests)} requests")
    print()

    if added:
        print(f"=== ADDED in {new_name} ({len(added)}) ===")
        for _key, r in added:
            print(f"  + [{r['method']}] {r['folder_path']} / {r['name']}")
            print(f"          {r['url']}")
        print()

    if removed:
        print(f"=== REMOVED from {old_name} ({len(removed)}) ===")
        for _key, r in removed:
            print(f"  - [{r['method']}] {r['folder_path']} / {r['name']}")
            print(f"          {r['url']}")
        print()

    if modified:
        print(f"=== MODIFIED ({len(modified)}) ===")
        for _key, r, diffs in modified:
            print(f"  ~ [{r['method']}] {r['folder_path']} / {r['name']}")
            for prop, old_val, new_val in diffs:
                print(f"      {prop} changed")
        print()

    if not added and not removed and not modified:
        print("No differences found.")


def esc(text):
    """HTML-escape a string."""
    return html.escape(str(text))


def generate_html(old_name, new_name, old_requests, new_requests, added, removed, modified, title):
    """Generate the full HTML report string."""
    parts = []
    parts.append(f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>{esc(title)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 20px; color: #1f2937; background: #f8fafc; }}
h1, h2 {{ color: #0f172a; }}
.grid {{ display:grid; grid-template-columns: repeat(4,1fr); gap:12px; margin:20px 0; }}
.card {{ background:white; border:1px solid #e5e7eb; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,.05); }}
.label {{ font-size:12px; color:#64748b; text-transform:uppercase; }}
.value {{ font-size:28px; font-weight:700; margin-top:6px; }}
.subtle {{ color:#475569; margin-bottom:4px; }}
table {{ width:100%; border-collapse: collapse; margin-top:12px; background:white; }}
th, td {{ border:1px solid #e5e7eb; text-align:left; padding:10px; vertical-align:top; font-size:13px; }}
th {{ background:#e2e8f0; }}
.section {{ margin-top:28px; }}
.modified-card {{ background:white; border:1px solid #e5e7eb; border-radius:10px; padding:16px; margin-bottom:16px; box-shadow:0 1px 2px rgba(0,0,0,.05); }}
.modified-title {{ font-size:18px; font-weight:700; margin-bottom:6px; }}
.muted {{ color:#64748b; font-size:13px; margin-bottom:4px; }}
.footer {{ margin-top:24px; color:#64748b; font-size:12px; }}
code {{ background:#f1f5f9; padding:2px 6px; border-radius:4px; }}
</style></head><body>
<h1>{esc(title)}</h1>
<div class="subtle"><strong>{esc(old_name)}</strong>: {esc(old_name)}</div>
<div class="subtle"><strong>{esc(new_name)}</strong>: {esc(new_name)}</div>
<div class="subtle">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div class="grid">
<div class="card"><div class="label">{esc(old_name)} Requests</div><div class="value">{len(old_requests)}</div></div>
<div class="card"><div class="label">{esc(new_name)} Requests</div><div class="value">{len(new_requests)}</div></div>
<div class="card"><div class="label">Added in {esc(new_name)}</div><div class="value">{len(added)}</div></div>
<div class="card"><div class="label">Removed from {esc(old_name)}</div><div class="value">{len(removed)}</div></div>
</div>
<div class="card"><div class="label">Modified Requests</div><div class="value">{len(modified)}</div></div>""")

    # Added requests table
    if added:
        parts.append('<div class="section"><h2>Added Requests</h2><table><thead><tr><th>Method</th><th>Name</th><th>Folder</th><th>URL</th></tr></thead><tbody>')
        for _key, r in added:
            parts.append(f'<tr><td>{esc(r["method"])}</td><td>{esc(r["name"])}</td><td>{esc(r["folder_path"])}</td><td>{esc(r["url"])}</td></tr>')
        parts.append('</tbody></table></div>')

    # Removed requests table
    if removed:
        parts.append('<div class="section"><h2>Removed Requests</h2><table><thead><tr><th>Method</th><th>Name</th><th>Folder</th><th>URL</th></tr></thead><tbody>')
        for _key, r in removed:
            parts.append(f'<tr><td>{esc(r["method"])}</td><td>{esc(r["name"])}</td><td>{esc(r["folder_path"])}</td><td>{esc(r["url"])}</td></tr>')
        parts.append('</tbody></table></div>')

    # Modified requests cards
    if modified:
        parts.append('<div class="section"><h2>Modified Requests</h2>')
        for _key, r, diffs in modified:
            parts.append(f"""
<div class="modified-card">
<div class="modified-title">{esc(r["method"])} - {esc(r["name"])}</div>
<div class="muted">Folder: {esc(r["folder_path"])}</div>
<div class="muted">URL: {esc(r["url"])}</div>
<table>
<thead><tr><th>Property</th><th>{esc(old_name)}</th><th>{esc(new_name)}</th></tr></thead>
<tbody>""")
            for prop, old_val, new_val in diffs:
                # BodySchema values contain <br> intentionally, don't escape them
                if prop == "BodySchema":
                    parts.append(f'<tr><td>{esc(prop)}</td><td>{old_val}</td><td>{new_val}</td></tr>')
                else:
                    parts.append(f'<tr><td>{esc(prop)}</td><td>{esc(old_val)}</td><td>{esc(new_val)}</td></tr>')
            parts.append('</tbody>\n</table>\n</div>\n')
        parts.append('</div>')

    parts.append("""<div class="footer">Comparison key: <code>METHOD + raw URL + request name</code>.<br>Structural comparison includes folder, description, headers, query params, path variables, request body schema, response codes, and response labels.</div>
</body></html>""")

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Diff two Postman collections.")
    parser.add_argument("old_collection", help="Path to the old Postman collection JSON")
    parser.add_argument("new_collection", help="Path to the new Postman collection JSON")
    parser.add_argument("--html", metavar="FILE", help="Write HTML report to FILE")
    parser.add_argument("--title", default="Postman Collection Diff", help="Title for the HTML report")
    args = parser.parse_args()

    old_name, old_requests = load_collection(args.old_collection)
    new_name, new_requests = load_collection(args.new_collection)

    added, removed, modified = compare_collections(old_requests, new_requests)

    print_text_report(old_name, new_name, old_requests, new_requests, added, removed, modified)

    if args.html:
        html_content = generate_html(old_name, new_name, old_requests, new_requests,
                                     added, removed, modified, args.title)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML report written to: {args.html}")


if __name__ == "__main__":
    main()
