'''
This script reads your Google service account JSON file and outputs a version
suitable for pasting directly into your .streamlit/secrets.toml.
It replaces all newlines in the JSON with '\\n' and escapes any existing backslashes,
so you can safely use it inside triple double quotes ("""...""") in TOML.
'''

import sys

# Usage: python convert_service_account_json_for_toml.py service_account.json

if len(sys.argv) != 2:
    print("Usage: python convert_service_account_json_for_toml.py service_account.json")
    sys.exit(1)

input_path = sys.argv[1]

with open(input_path, "r") as infile:
    json_str = infile.read()

# Escape all existing backslashes (to avoid double-escaping)
json_str = json_str.replace("\\", "\\\\")
# Replace all newlines with \n
json_str = json_str.replace("\n", "\\n")

print("\nPaste the following into your .streamlit/secrets.toml (inside triple double quotes):\n")
print(json_str)