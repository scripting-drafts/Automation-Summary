import json
import random
import requests
import matplotlib.pyplot as plt
from matplotlib.backend_bases import MouseEvent

# ---- Load Bookmarks ----
BOOKMARK_FILE = "bookmarks-2025-06-19.json"

def extract_bookmark_urls(node):
    urls = []
    if isinstance(node, dict):
        if "children" in node:
            for child in node["children"]:
                urls.extend(extract_bookmark_urls(child))
        elif "url" in node and "title" in node:
            urls.append((node["title"], node["url"]))
    elif isinstance(node, list):
        for item in node:
            urls.extend(extract_bookmark_urls(item))
    return urls

with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
    bookmarks_data = json.load(f)

bookmark_urls = extract_bookmark_urls(bookmarks_data)

# ---- Check Status ----
def check_url_status(url, timeout=5):
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False

print("Checking bookmark statuses... this might take a minute...")
status_results = []
for title, url in bookmark_urls:
    status = check_url_status(url)
    status_results.append((title, url, status))

# ---- Generate Dot Cloud ----
positions = {i: (random.uniform(0, 1), random.uniform(0, 1)) for i in range(len(status_results))}
colors = ['green' if status else 'red' for _, _, status in status_results]
titles = [title for title, _, _ in status_results]

fig, ax = plt.subplots(figsize=(14, 9))

x_vals = [p[0] for p in positions.values()]
y_vals = [p[1] for p in positions.values()]

sc = ax.scatter(x_vals, y_vals, c=colors, s=120, edgecolor='black', linewidth=0.5)

annot = ax.annotate("", xy=(0, 0), xytext=(15, 15),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="white"),
                    arrowprops=dict(arrowstyle="->"))
annot.set_visible(False)

def update_annot(ind):
    i = ind["ind"][0]
    pos = x_vals[i], y_vals[i]
    annot.xy = pos
    text = f"{titles[i]}"
    annot.set_text(text)
    annot.get_bbox_patch().set_facecolor(colors[i])
    annot.get_bbox_patch().set_alpha(0.9)

def hover(event: MouseEvent):
    vis = annot.get_visible()
    if event.inaxes == ax:
        cont, ind = sc.contains(event)
        if cont:
            update_annot(ind)
            annot.set_visible(True)
            fig.canvas.draw_idle()
        elif vis:
            annot.set_visible(False)
            fig.canvas.draw_idle()

fig.canvas.mpl_connect("motion_notify_event", hover)

ax.set_title("Bookmark Status Cloud - Hover to See Titles", fontsize=16)
ax.set_xticks([])
ax.set_yticks([])
ax.set_xlim(0, 1.05)
ax.set_ylim(0, 1.05)
for spine in ax.spines.values():
    spine.set_visible(False)

plt.tight_layout()
plt.show()
