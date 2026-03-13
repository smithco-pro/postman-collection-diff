# postman-collection-diff

Compare two Postman collection JSON files and generate detailed diff reports showing added, removed, and modified API requests.

## Features

- Zero dependencies — pure Python 3 standard library
- Recursively handles nested Postman collection folders
- Identifies added, removed, and modified requests
- Detects changes in folder path, description, body schema, response codes, and response names
- Text summary to stdout, optional styled HTML report
- Comparison key: HTTP method + URL + request name

## Usage

Generate a text report to the console:

```
python Compare-PostmanCollections.py old.json new.json
```

Generate a styled HTML report:

```
python Compare-PostmanCollections.py old.json new.json --html report.html --title "v24 vs v25"
```

| Argument | Description |
|---|---|
| `old_collection` | Path to the old Postman collection JSON |
| `new_collection` | Path to the new Postman collection JSON |
| `--html FILE` | Write an HTML report to FILE |
| `--title TEXT` | Report title (default: "Postman Collection Diff") |

## Example Output

See [Example-Output.html](Example-Output.html) for a sample HTML report comparing Workspace ONE UEM API collections (v2406 vs v2506): 894 to 909 requests, with 58 added, 43 removed, and 48 modified.

## How It Works

Requests are extracted recursively from the Postman collection JSON structure. Each request is uniquely identified by its HTTP method, raw URL, and name. Requests present in both collections are compared field-by-field across folder path, description, body schema (extracted as JSONPath-style type mappings), response codes, and response names.

## License

[MIT](LICENSE)
