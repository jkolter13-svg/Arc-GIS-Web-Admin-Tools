# =============================================================================
# ITEM INVENTORY SCRIPT
# =============================================================================
# PURPOSE:
#   Connect to an ArcGIS portal (AGOL or Enterprise) using your active ArcGIS
#   Pro sign-in, scan every item in that portal (or every item owned by a
#   specific user), and write a CSV file containing each item's title, type,
#   ID, summary, and description.
#
# SAFETY:
#   This script is 100% READ-ONLY with respect to your portal.
#   It uses only GET requests — it never calls .update(), .delete(), .add(),
#   .publish(), or any other method that would change anything in your portal.
#   The ONLY thing written is one CSV file on YOUR LOCAL MACHINE.
#
# HOW TO RUN:
#   Paste into the ArcGIS Pro Python window, or an ArcGIS Notebook inside Pro.
#   Make sure you are signed into the portal you want to inventory in Pro first.
#   Before running, set the two configuration variables in Section 2:
#     OUTPUT_FILE_PATH — where to save the CSV on your local machine.
#     ITEM_OWNER       — a portal username to filter by, or "" for all items.
#
# REQUIREMENTS:
#   ArcGIS API for Python 2.4.x (ships with ArcGIS Pro 3.x)
#
# CREDITS:
#   Original code by (C) 2019 Joshua Sharp-Heward, Whangarei, New Zealand
#   Released under GNU Lesser Public License v3.0 (GPLv3)
#   email jsh726@uowmail.edu.au
#   linkedin https://www.linkedin.com/in/joshua-sharp-heward-89b129131/
#   Modified, Updated, and Commented By: Jonathan Kolterman 2026
#   email jkolterman13@gmail.com
#   linkedin https://www.linkedin.com/in/jonathan-kolterman-1808342b8
# =============================================================================
 
 
# -----------------------------------------------------------------------------
# IMPORTS
# These lines load the external code libraries this script depends on.
# None of these imports cause any network calls or side effects on their own —
# they just make functionality available for use later in the script.
# -----------------------------------------------------------------------------
 
from arcgis.gis import GIS
# ^^^ Loads the GIS class from Esri's ArcGIS API for Python.
#     GIS is the main entry point — it represents a connection to a portal
#     (either ArcGIS Online or ArcGIS Enterprise). We use it to authenticate
#     and to search for items.
 
import csv
# ^^^ Python's built-in CSV module. Used at the end of the script to write
#     results to a .csv file on your local machine. Part of Python's standard
#     library — no installation needed, nothing network-related.
 
import os
# ^^^ Python's built-in operating system interface module. We use it for
#     os.path.expanduser("~") and os.path.join() to build the correct file
#     path to your Documents folder regardless of your Windows username, and
#     os.startfile() to open the finished CSV automatically when done.
#     Part of Python's standard library — no installation needed.
 
 
# =============================================================================
# SECTION 1 — PORTAL CONNECTION
# =============================================================================
# This section establishes the connection to your ArcGIS portal.
# It is READ-ONLY — connecting to a portal does not modify anything.
# =============================================================================
 
gis = GIS('pro')
# ^^^ Creates a GIS connection object and stores it in the variable 'gis'.
#     The argument 'pro' is a special keyword that tells the API:
#     "don't ask me for a username/password — instead, use the portal that
#     the user is already signed into inside ArcGIS Pro."
#     This means no credentials are stored in or transmitted by this script.
#     The resulting 'gis' object is what we use for all portal interactions.
#
#     ALTERNATIVES (swap this line if needed):
#       gis = GIS('home')
#           Use this if running from an ArcGIS Notebook inside AGOL/Enterprise
#           rather than from ArcGIS Pro. 'home' means "use the portal this
#           notebook is hosted on."
#
#       gis = GIS("https://your-enterprise.com/portal")
#           Use this to explicitly target a specific Enterprise portal URL.
#           You will be prompted for credentials if Pro's session doesn't
#           already match that portal.
 
print(f"\nConnected to portal : {gis.properties.portalHostname}")
print(f"Signed in as        : {gis.properties['user']['username']}\n")
# ^^^ Print a confirmation of which portal we connected to and who we are
#     signed in as. Useful to verify you're pointed at the right environment
#     before a potentially long-running inventory scan.
#     gis.properties is a dict-like object of portal metadata (read-only).
#     .portalHostname is the domain of the portal, e.g. "myorg.maps.arcgis.com".
 
 
# =============================================================================
# SECTION 2 — CONFIGURATION
# =============================================================================
# Set these two variables before running the script.
# Everything else is automatic.
# =============================================================================
 
OUTPUT_FILE_PATH = os.path.join(os.path.expanduser("~/Documents"), "item_inventory.csv")
# ^^^ The full path to the CSV file that will be created on your local machine.
#     os.path.expanduser("~") resolves to your Windows user profile folder,
#     e.g. "C:\Users\YourName". os.path.join then appends "\Documents\item_inventory.csv".
#     Result example: "C:\Users\YourName\Documents\item_inventory.csv"
#
#     To save somewhere else, replace this with a literal path string, e.g.:
#       OUTPUT_FILE_PATH = r"C:\GIS\Reports\item_inventory.csv"
#     The r prefix makes it a raw string so backslashes are treated literally.
 
ITEM_OWNER = ""
# ^^^ Optional: set this to a portal username string to limit the scan to items
#     owned by that one user. Leave as "" (empty string) to scan ALL items in
#     the portal regardless of owner.
#
#     Examples:
#       ITEM_OWNER = ""              → scan everything in the portal
#       ITEM_OWNER = "jkolterman"    → scan only items owned by jkolterman
 
# Item types to exclude from the report.
# These types tend to be auto-generated system attachments or low-value entries
# that add noise to an inventory report without providing useful information.
EXCLUDED_TYPES = {
    'Code Attachment',
    'Mobile Map Package',
    'Layer Template',
    'Mobile Application',
}
# ^^^ A Python set (not a list) is used here for membership testing.
#     Checking 'if x in some_set' is O(1) — constant time regardless of how
#     many types are in the set. A list would be O(n) — slower for large lists.
#     Add or remove type strings here to adjust what gets filtered out.
#     Type strings must match exactly the values returned by item.type.
 
 
# =============================================================================
# SECTION 3 — SEARCH FOR ITEMS
# =============================================================================
# This section queries the portal for items based on the ITEM_OWNER setting
# configured above. It is READ-ONLY — .search() sends only GET requests.
# =============================================================================
 
if ITEM_OWNER:
    # ^^^ If ITEM_OWNER is a non-empty string, filter the search to that user.
    #     Python treats any non-empty string as truthy, so 'if ITEM_OWNER:'
    #     is equivalent to 'if len(ITEM_OWNER) > 0:'.
 
    print(f"Scanning items owned by '{ITEM_OWNER}'...\n")
    items = gis.content.search(query=f"owner:{ITEM_OWNER}", max_items=10000)
    # ^^^ The query "owner:username" is an ArcGIS portal search keyword that
    #     returns only items belonging to the specified user.
    #     max_items=10000 raises the default cap of 100 to avoid silent
    #     truncation on large portals.
 
else:
    print("Scanning ALL items in the portal...\n")
    items = gis.content.search(query="", max_items=10000)
    # ^^^ Empty query string with no type filter returns every item in the
    #     portal the signed-in user has permission to see, up to max_items.
    #     If your portal has more than 10,000 items, raise max_items further
    #     or consider paginating with multiple searches.
 
print(f"Found {len(items)} item(s) before filtering. Applying type exclusions...\n")
# ^^^ Report the raw count before we filter out excluded types, so you can
#     see how many items the search returned versus how many end up in the CSV.
 
 
# =============================================================================
# SECTION 4 — BUILD THE ITEM METADATA COLLECTION
# =============================================================================
# This section loops over every item returned by the search, skips excluded
# types, and collects the fields we want to report on into a list of dicts.
#
# SAFE: All attribute access here reads data already returned by .search().
#       No additional network calls are made per item — the fields we need
#       (title, type, id, snippet, description) are included in the search
#       response payload.
# =============================================================================
 
item_rows = []
# ^^^ An empty list that will accumulate one dict per item we want to report.
#     Using a list (rather than the original dict-of-dicts keyed by ID) keeps
#     the structure simple and maps directly to csv.DictWriter rows later.
 
for item in items:
    # ^^^ Loop over every Item object returned by the search above.
    #     'item' is a temporary variable holding the current Item object.
 
    if item.type in EXCLUDED_TYPES:
        # ^^^ Check whether this item's type is in our exclusion set.
        #     If it is, skip it entirely — don't add it to item_rows.
 
        continue
        # ^^^ 'continue' skips the rest of this loop iteration and jumps
        #     straight to the next item in the list.
 
    summary = item['snippet'] or ""
    # ^^^ item['snippet'] reads the item's short summary text.
    #     The 'or ""' means: if snippet is None (not set), use an empty
    #     string instead, so the CSV cell is blank rather than the word "None".
 
    description = item['description'] or ""
    # ^^^ Same pattern for the item's long-form description field.
    #     Descriptions can contain HTML markup — that will be preserved as-is
    #     in the CSV. Strip or sanitize here if you want plain text output.
 
    item_rows.append({
        'title':       item.title,
        # ^^^ The display name of the item as it appears in the portal.
 
        'type':        item.type,
        # ^^^ The Esri item type string, e.g. "Feature Service", "Web Map",
        #     "Dashboard", "Survey123", "StoryMap", etc.
 
        'id':          item.id,
        # ^^^ The unique 32-character GUID identifier for this item in the portal.
        #     Can be appended to the portal home URL to build a direct link:
        #     https://yourportal.com/home/item.html?id=<item.id>
 
        'summary':     summary,
        # ^^^ The item's short summary / snippet text (if any).
 
        'description': description
        # ^^^ The item's full description text (if any). May contain HTML.
    })
 
print(f"{len(item_rows)} item(s) remain after filtering. Writing CSV...\n")
# ^^^ Report how many items survived the type exclusion filter.
#     The difference between this number and the earlier count tells you
#     how many items were excluded.
 
 
# =============================================================================
# SECTION 5 — WRITE RESULTS TO CSV ON YOUR LOCAL MACHINE
# =============================================================================
# Writes one CSV file to the path set in OUTPUT_FILE_PATH above.
# One row per item, with columns: title, type, id, summary, description.
#
# SAFE: This file is written to YOUR LOCAL MACHINE ONLY.
#       Nothing is uploaded, published, or sent to any portal.
#       No portal items, services, or configurations are touched.
# =============================================================================
 
with open(OUTPUT_FILE_PATH, mode='w', newline='', encoding='utf-8') as f:
# ^^^ open() creates (or overwrites) the file at OUTPUT_FILE_PATH.
#     mode='w'         : write mode — creates the file if it doesn't exist,
#                        overwrites it if it does.
#     newline=''       : required by Python's csv module on Windows to prevent
#                        it from writing extra blank lines between every row.
#     encoding='utf-8' : ensures item names/descriptions with special characters
#                        (accents, symbols, HTML entities) are written correctly.
#     The 'with' statement ensures the file is properly closed and saved even
#     if something goes wrong — no risk of a half-written, corrupted file.
 
    writer = csv.DictWriter(
    # ^^^ DictWriter lets us write dicts directly as rows. Each key in the dict
    #     maps to a column name specified in fieldnames below.
 
        f,
        # ^^^ 'f' is the file object opened by the 'with' statement above.
 
        fieldnames=['title', 'type', 'id', 'summary', 'description']
        # ^^^ The column names for the CSV header row, in the order they'll appear.
        #     These must exactly match the keys used in the dicts in item_rows.
    )
    writer.writeheader()
    # ^^^ Writes the column name row as the first line of the CSV file.
    #     Without this, the CSV would have no header and be hard to read in Excel.
 
    writer.writerows(item_rows)
    # ^^^ Writes all rows in item_rows to the file in one call.
    #     Each dict in item_rows becomes one row, with values placed in the
    #     columns matching their keys. Much faster than looping and writing
    #     one row at a time.
 
 
# =============================================================================
# SECTION 6 — CONFIRMATION AND OPEN FILE
# =============================================================================
 
print(f"CSV written to: {OUTPUT_FILE_PATH}")
print(f"Total items exported: {len(item_rows)}")
print("\nDone. No portal items were modified.")
# ^^^ Explicit confirmation that the script completed without touching the portal.
 
#os.startfile(OUTPUT_FILE_PATH)
# ^^^ Opens the finished CSV file using whatever application Windows has
#     associated with .csv files (typically Microsoft Excel or Notepad).
#     This is a convenience step — comment it out if you don't want the
#     file to open automatically, or if running on a non-Windows machine
#     (os.startfile() is Windows-only; on macOS/Linux use subprocess.call
#     with 'open' or 'xdg-open' respectively).
