"""Copy an existing OpenCode API key into 1Password via stdin."""

from __future__ import annotations

import argparse
import json

from jev_demo.client import _op, read_opencode_key


def _json_command(args: list[str], *, input_text: str | None = None):
    code, out, _ = _op(args, input_text=input_text)
    if code:
        # CLI error bodies can contain input values; report only the operation.
        raise RuntimeError(f"1Password {' '.join(args[:2])} failed. Check CLI sign-in and vault access.")
    try:
        return json.loads(out)
    except ValueError:
        raise RuntimeError("1Password returned an invalid JSON response") from None


def store_opencode_key(vault: str, title: str = "OpenCode") -> dict[str, str]:
    key, source = read_opencode_key()
    if not key:
        raise RuntimeError(source)

    entries = _json_command(["item", "list", "--vault", vault, "--format", "json"])
    matches = [entry for entry in entries if entry.get("title") == title]
    if len(matches) > 1:
        raise RuntimeError("Multiple destination items have this title; choose a unique --title.")
    if matches:
        item = _json_command(["item", "get", matches[0]["id"], "--vault", vault, "--format", "json"])
        stored = next((f.get("value") for f in item.get("fields", []) if f.get("id") == "credential"), None)
        if stored != key:
            raise RuntimeError("The destination item contains a different credential; it was left unchanged.")
        action = "already stored"
    else:
        template = _json_command(["item", "template", "get", "API Credential"])
        template["title"] = title
        template["urls"] = [{"href": "https://opencode.ai", "primary": True}]
        for field in template["fields"]:
            if field["id"] == "credential":
                field["value"] = key
            elif field["id"] == "notesPlain":
                field["value"] = f"Copied from {source}. Used with the OpenCode API."
        # No secret in argv, an environment variable, a temporary file, or stdout.
        item = _json_command(
            ["item", "create", "--vault", vault, "--format", "json", "-"],
            input_text=json.dumps(template),
        )
        action = "created"

    reference = f"op://{item['vault']['id']}/{item['id']}/credential"
    code, stored, _ = _op(["read", reference])
    if code or stored != key:
        raise RuntimeError("The item exists, but reading back its credential failed.")
    return {"action": action, "item": title, "reference": reference}


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy the local OpenCode API key into 1Password.")
    parser.add_argument("--vault", required=True, help="Destination vault name or ID")
    parser.add_argument("--title", default="OpenCode", help="Destination item title (default: OpenCode)")
    args = parser.parse_args()
    try:
        result = store_opencode_key(args.vault, args.title)
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
