import json
import os
import requests
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
WHITE = "\033[97m"
CYAN = "\033[96m"
RESET = "\033[0m"

def check_url_status(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=3)
        if 200 <= response.status_code < 400:
            return f"{GREEN}🟢{RESET}"
        else:
            return f"{RED}🔴{RESET}"
    except:
        return f"{RED}🔴{RESET}"

def collect_bookmarks_flat(items, flat_list):
    for item in items:
        if item.get("type") == "text/x-moz-place":
            url = item.get("uri", "")
            title = item.get("title", "No Title")
            if url:  # Skip empty entries
                flat_list.append((title, url))
        elif "children" in item:
            collect_bookmarks_flat(item["children"], flat_list)

def display_flat_bookmarks(bookmarks):
    for title, url in bookmarks:
        status = check_url_status(url)
        print(f"{status} {CYAN}{url:50}{RESET} 🔗 {title}")

if __name__ == "__main__":
    json_file = sys.argv[1] if len(sys.argv) > 1 else "bookmarks.json"
    if not os.path.exists(json_file):
        print("❌ Bookmark JSON file not found.")
        sys.exit(1)

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    flat_bookmarks = []
    collect_bookmarks_flat(data["children"], flat_bookmarks)

    print(f"\n📚 Flat Bookmark Status Report ({len(flat_bookmarks)} entries):\n")
    display_flat_bookmarks(flat_bookmarks)
