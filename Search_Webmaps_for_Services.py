# =============================================================================
# SERVICE INVENTORY SCRIPT
# =============================================================================
# PURPOSE:
#   Connect to an ArcGIS portal (AGOL or Enterprise) using your active ArcGIS
#   Pro sign-in, find every Web Map in that portal, and extract every service
#   URL referenced by every layer in every one of those maps. Output is saved
#   as two CSV files on your local machine.
#
# SAFETY:
#   This script is 100% READ-ONLY with respect to your portals.
#   It uses only GET requests — it never calls .update(), .delete(), .add(),
#   .publish(), or any other method that would change anything in your portal.
#   The ONLY things written are two CSV files on YOUR LOCAL MACHINE.
#
# HOW TO RUN:
#   Paste into the ArcGIS Pro Python window, or an ArcGIS Notebook inside Pro.
#   Make sure you are signed into the portal you want to inventory in Pro first.
#
# REQUIREMENTS:
#   ArcGIS API for Python 2.4.x (ships with ArcGIS Pro 3.x)
# CREDITS:
#   origional code by (C) 2019 Joshua Sharp-Heward, Whangarei, New Zealand
#   released under GNU Lesser Public License v3.0 (GPLv3)
#   email jsh726@uowmail.edu.au
#   linkedin https://www.linkedin.com/in/joshua-sharp-heward-89b129131/
#   Modified and Updated and Commented By: Jonathan Kolterman 2026
#   email jkolterman13@gmail.com
#   linkedin https://www.linkedin.com/in/jonathan-kolterman-1808342b8
# =============================================================================


# -----------------------------------------------------------------------------
# IMPORTS
# These three lines load the external code libraries this script depends on.
# None of these imports cause any network calls or side effects on their own —
# they just make functionality available for use later in the script.
# -----------------------------------------------------------------------------

from arcgis.gis import GIS
# ^^^ Loads the GIS class from Esri's ArcGIS API for Python.
#     GIS is the main entry point — it represents a connection to a portal
#     (either ArcGIS Online or ArcGIS Enterprise). We use it to authenticate
#     and to search for items. This is the only arcgis module we need in 2.4.x
#     since we're reading raw JSON instead of using the old WebMap class.

import csv
# ^^^ Python's built-in CSV module. Used at the end of the script to write
#     results to .csv files on your local machine. Part of Python's standard
#     library — no installation needed, nothing network-related.

import os
# ^^^ Python's built-in operating system interface module. We use it for one
#     thing: os.path.expanduser("~") and os.path.join() to build the correct
#     file path to your Documents folder regardless of your Windows username.
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


# =============================================================================
# SECTION 2 — RECURSIVE LAYER FLATTENER FUNCTION
# =============================================================================
# This section DEFINES a function — it does not run yet.
# The function is called later in Section 5 for each web map found.
# =============================================================================

def unnest_layers(layer_list):
    # -------------------------------------------------------------------------
    # WHAT THIS FUNCTION DOES:
    #   Web Maps can contain "Group Layers" — layers that act as folders and
    #   contain other layers nested inside them. A simple loop over the top-level
    #   layer list would completely miss anything inside a group.
    #
    #   This function solves that by recursing: if it finds a layer that has
    #   child layers inside it, it calls itself on those children, and keeps
    #   going until it reaches layers with no further children (leaf layers).
    #   It returns one flat list containing every individual layer found,
    #   no matter how deeply nested.
    #
    # PARAMETERS:
    #   layer_list : a Python list of dicts, where each dict describes one layer.
    #                This comes from the web map's JSON under 'operationalLayers',
    #                or from a group layer's nested 'layers' key.
    #
    # RETURNS:
    #   A flat Python list of dicts, one dict per individual (non-group) layer.
    #
    # SAFE: This function only reads Python dicts. It makes zero network calls
    #       and modifies nothing — not the dicts, not the portal, nothing.
    # -------------------------------------------------------------------------

    flat = []
    # ^^^ This is our accumulator — an empty list we'll add layers to as we
    #     find them. Every leaf layer discovered gets appended here.
    #     'flat' is a local variable that only exists while this function runs.

    for lyr in layer_list:
        # ^^^ Loop over every layer dict in the list we were given.
        #     'lyr' is a temporary variable holding the current layer dict.

        try:
            # ^^^ try/except means: attempt the indented code, and if anything
            #     goes wrong (any kind of error), jump to the 'except' block
            #     instead of crashing the whole script.

            if 'layers' in lyr:
                # ^^^ Check whether this layer dict has a 'layers' key inside it.
                #     In ArcGIS web map JSON, group layers have a 'layers' key
                #     that holds a list of their child layers.
                #     If 'layers' is present, this is a group — not a leaf layer.

                flat += unnest_layers(lyr['layers'])
                # ^^^ RECURSION: call this same function again, but passing in
                #     the child layers list instead of the current list.
                #     Whatever flat list comes back from that recursive call,
                #     append all of it onto our current flat list using +=.
                #     This keeps going until there are no more nested groups.

            else:
                flat.append(lyr)
                # ^^^ No 'layers' key means this is a leaf layer (FeatureLayer,
                #     MapServiceLayer, ImageServiceLayer, WMSLayer, etc.).
                #     Add it directly to our flat results list.

        except Exception as e:
            # ^^^ If anything went wrong inspecting this layer (malformed dict,
            #     unexpected data type, missing key, etc.) — catch the error,
            #     print a warning, and continue to the next layer.
            #     We never want one bad layer to crash the whole inventory run.
            print(f"  [warn] Skipping a layer due to error: {e}")
            # ^^^ f-string: the {e} gets replaced with the actual error message.

    return flat
    # ^^^ Hand back the completed flat list to whoever called this function.


# =============================================================================
# SECTION 3 — LAYER URL RESOLVER FUNCTION
# =============================================================================
# This section DEFINES a function — it does not run yet.
# The function is called later in Section 5 for each layer found.
# =============================================================================

def get_layer_url(lyr_dict):
    # -------------------------------------------------------------------------
    # WHAT THIS FUNCTION DOES:
    #   Most layer types (FeatureLayer, MapServiceLayer, etc.) store their
    #   service endpoint URL in a key called 'url' inside their JSON dict.
    #
    #   Vector Tile Layers are an exception — they use 'styleUrl' instead of
    #   'url'. Trying to read 'url' from a VectorTileLayer returns nothing.
    #   This is the bug the original forum thread was about.
    #
    #   This function checks the layer type first, then reads the correct key,
    #   so we always get a URL regardless of layer type.
    #   If neither key exists, it returns the string 'NO_URL' as a placeholder
    #   so the CSV always has a readable value in that column rather than blank.
    #
    # PARAMETERS:
    #   lyr_dict : a single layer dict from the web map JSON.
    #
    # RETURNS:
    #   A string containing the service URL, or 'NO_URL' if none was found.
    #
    # SAFE: Pure Python dict reads. No network calls, no modifications.
    # -------------------------------------------------------------------------

    layer_type = lyr_dict.get('layerType', '')
    # ^^^ Read the 'layerType' value from the layer dict.
    #     .get('layerType', '') means: try to get the value for key 'layerType';
    #     if that key doesn't exist in the dict, return '' (empty string) instead
    #     of throwing a KeyError. This makes the code safe for malformed layers.
    #     Examples of layerType values: 'ArcGISFeatureLayer', 'VectorTileLayer',
    #     'ArcGISMapServiceLayer', 'ArcGISImageServiceLayer', 'WMS', etc.

    if layer_type == 'VectorTileLayer':
        # ^^^ Check if this is specifically a Vector Tile Layer.
        #     If it is, we need to look in 'styleUrl' instead of 'url'.

        return lyr_dict.get('styleUrl', 'NO_URL')
        # ^^^ Read 'styleUrl' from the dict. If it's missing, return 'NO_URL'.
        #     'return' immediately exits the function with this value.

    return lyr_dict.get('url', 'NO_URL')
    # ^^^ For all other layer types: read 'url' from the dict.
    #     If 'url' is missing (unusual but possible for some layer types like
    #     annotation layers or unsupported types), return 'NO_URL'.
    #     This line is only reached if the layer was NOT a VectorTileLayer.


# =============================================================================
# SECTION 4 — SEARCH FOR ALL WEB MAPS
# =============================================================================
# This section queries the portal for every Web Map item it contains.
# It is READ-ONLY — .search() sends a GET request and returns results.
# Nothing is created, modified, or deleted.
# =============================================================================

print(f"\nConnected to portal: {gis.properties.portalHostname}")
# ^^^ Print a confirmation of which portal we connected to.
#     gis.properties is a dict-like object of portal metadata (read-only).
#     .portalHostname is the domain name of the portal, e.g. "myorg.maps.arcgis.com"
#     or "enterprise.mycompany.com". This is just for your information —
#     useful to confirm you're pointed at the right environment.

print("Searching for all Web Maps — this may take a moment on large portals...\n")
# ^^^ Simple status message so you know the script is running and not frozen.

web_maps = gis.content.search(
# ^^^ gis.content is the content manager for the connected portal.
#     .search() sends a read-only REST API GET request to the portal's
#     item search endpoint. It returns a list of Item objects.
#     SAFE: this is equivalent to typing in the portal's search box.
#     It cannot create or modify anything.

    query="",
    # ^^^ The search query string. Empty string "" means "no filter on title or
    #     tags" — return everything. If you wanted to narrow results you could
    #     use something like query="owner:myusername" or query="title:roads".
    #     We leave it empty to get a complete inventory.

    item_type="Web Map",
    # ^^^ Filter results to only items of type "Web Map". This excludes Feature
    #     Services, Dashboards, Story Maps, etc. We only want Web Maps because
    #     that's where layer references live. Without this filter we'd get every
    #     item in the portal.

    max_items=10000
    # ^^^ The default maximum number of results .search() returns is 100.
    #     For any org with more than 100 web maps, the default would silently
    #     truncate results and you'd miss items. 10000 raises that ceiling.
    #     If your org somehow has more than 10,000 web maps, raise this further.
)

print(f"Found {len(web_maps)} web map(s). Extracting layers...\n")
# ^^^ len(web_maps) counts how many Web Map items were returned.
#     Printed so you can see progress and sanity-check the result count.


# =============================================================================
# SECTION 5 — EXTRACT ALL LAYERS FROM EVERY WEB MAP
# =============================================================================
# This is the main processing loop. For each Web Map found in Section 4,
# we fetch its full JSON definition, extract all layer references, and store
# the results in a list.
#
# SAFE: item.get_data() sends a read-only REST GET request to fetch the item's
#       stored JSON. It is the same underlying data the old WebMap() class used
#       to fetch internally. No writes occur at any point in this section.
# =============================================================================

results = []
# ^^^ An empty list that will accumulate one dict for every layer reference
#     found across all web maps. By the end of the loop this list may contain
#     thousands of entries if your org has many maps with many layers.

for item in web_maps:
    # ^^^ Loop over every Web Map item returned by the search in Section 4.
    #     'item' is a temporary variable holding the current Item object.

    try:
        # ^^^ Wrap the entire per-map logic in try/except so that if one web
        #     map fails for any reason (bad JSON, permissions, network hiccup),
        #     we log the error and continue to the next map rather than crashing.

        data = item.get_data()
        # ^^^ Fetches the web map's full JSON definition from the portal.
        #     Every Web Map item stores its configuration (layer list, basemap,
        #     bookmarks, popups, etc.) as a JSON blob in the portal.
        #     .get_data() sends a read-only REST GET request to retrieve that
        #     blob and returns it as a Python dict.
        #     SAFE: this is a GET request only. It reads the item's stored
        #     definition but does not open, modify, or re-save anything.

        if not data:
            # ^^^ Some web map items exist in the portal but have no stored
            #     JSON (empty maps, broken items, items still being created).
            #     If get_data() returns None or an empty dict, skip this item
            #     rather than crashing when we try to read keys from it.
            print(f"  [skip] '{item.title}' returned no data")
            continue
            # ^^^ 'continue' skips the rest of this loop iteration and jumps
            #     straight to the next item in the web_maps list.

        operational_layers = data.get('operationalLayers', [])
        # ^^^ Read the 'operationalLayers' list from the web map JSON.
        #     'operationalLayers' is the standard ArcGIS JSON key for all the
        #     user-added layers in a web map — Feature Layers, Map Services,
        #     WMS layers, etc. This is distinct from basemap layers.
        #     .get('operationalLayers', []) means: if this key is missing
        #     (e.g. an empty map), return an empty list instead of crashing.
        #
        #     NOTE: Basemap layers are stored separately under:
        #       data['baseMap']['baseMapLayers']
        #     We're not reading those here because we're inventorying operational
        #     services, not basemap tiles. You could add basemap layer extraction
        #     here if needed.

        flat_layers = unnest_layers(operational_layers)
        # ^^^ Call the function we defined in Section 2, passing in the list of
        #     operational layers for this web map. This recursively flattens any
        #     group layers and returns a single flat list of all leaf layers.
        #     The result is stored in 'flat_layers'.

        for lyr in flat_layers:
            # ^^^ Loop over every individual (non-group) layer in this web map.

            url = get_layer_url(lyr)
            # ^^^ Call the function from Section 3 to get the service URL for
            #     this layer, handling the VectorTileLayer edge case cleanly.

            results.append({
            # ^^^ Build a dict describing this layer reference and add it to
            #     the results list. Each key becomes a column in the CSV later.

                'webmap_title': item.title,
                # ^^^ The display name of the web map this layer came from.
                #     item.title reads from the item's metadata (already loaded
                #     by .search() — no extra network call needed).

                'webmap_id':    item.id,
                # ^^^ The unique GUID identifier of the web map item in the portal.
                #     Format: 32-character hex string like "a1b2c3d4e5f6...".
                #     Useful for building direct portal URLs to the item later.

                'layer_title':  lyr.get('title', lyr.get('id', 'UNKNOWN')),
                # ^^^ The display name of this layer as it appears in the map.
                #     Most layers have a 'title' key. If 'title' is missing,
                #     fall back to 'id' (the layer's internal identifier).
                #     If neither exists, use 'UNKNOWN' as a last resort.

                'layer_type':   lyr.get('layerType', 'UNKNOWN'),
                # ^^^ The type of this layer. Examples: 'ArcGISFeatureLayer',
                #     'VectorTileLayer', 'ArcGISMapServiceLayer', 'WMS', etc.
                #     Useful for filtering the CSV later (e.g. show only feature
                #     services, or only WMS layers).

                'layer_url':    url
                # ^^^ The service endpoint URL resolved in the line above.
                #     This is the actual REST URL of the backing service.
                #     Examples:
                #       https://services.arcgis.com/.../FeatureServer/0
                #       https://enterprise.co.com/server/rest/services/.../MapServer
            })

    except Exception as e:
        # ^^^ If anything went wrong processing this entire web map, catch the
        #     error, print a message identifying which map failed, and continue
        #     to the next map. One broken map should never abort the whole run.
        print(f"  [error] Could not process web map '{item.title}': {e}")


# =============================================================================
# SECTION 6 — DEDUPLICATE SERVICE URLs
# =============================================================================
# The same service (e.g. a parcel boundary layer) often appears in many
# different web maps. The 'results' list above records every occurrence with
# its map context. This section produces a clean, deduplicated list of just
# the unique service URLs — your actual service inventory.
#
# SAFE: Pure Python set and sort operations. No network calls whatsoever.
# =============================================================================

unique_urls = sorted(set(
# ^^^ sorted() arranges the results alphabetically so the list is easier to
#     read and scan. set() is what does the deduplication — a Python set
#     automatically discards duplicate values, keeping only one copy of each.

    r['layer_url']
    # ^^^ For each result dict 'r' in the results list, extract just the URL.

    for r in results
    # ^^^ This is a "generator expression" — a compact way to loop over results.

    if r['layer_url'] not in ('NO_URL', None, '')
    # ^^^ Filter out placeholder values. We only want real URLs in the unique
    #     list. Layers without a URL are still in the full results CSV but are
    #     excluded from the unique services list since they have no endpoint.
))


# =============================================================================
# SECTION 7 — PRINT SUMMARY TO CONSOLE
# =============================================================================
# Prints a summary of findings to the Python window / notebook output.
# SAFE: print() only — no side effects of any kind.
# =============================================================================

print(f"\n{'='*60}")
# ^^^ Print a visual divider line. '='*60 produces a string of 60 '=' characters.

print(f"TOTAL LAYER REFERENCES FOUND : {len(results)}")
# ^^^ Total count of all layer rows collected — including duplicates across maps.

print(f"  (same service may appear multiple times across different maps)")

print(f"UNIQUE SERVICE URLs          : {len(unique_urls)}")
# ^^^ Count of deduplicated URLs — this is the size of your actual service inventory.

print(f"  (this is your actual service inventory)")
print(f"{'='*60}\n")

print("── Unique Service URLs ──")
for url in unique_urls:
    print(f"  {url}")
    # ^^^ Print each unique service URL, indented two spaces for readability.


# =============================================================================
# SECTION 8 — EXPORT RESULTS TO CSV FILES ON YOUR LOCAL MACHINE
# =============================================================================
# Writes two CSV files to your Windows Documents folder.
#
# FILE 1: all_layers.csv
#   One row per layer reference, with the web map context included.
#   Use this to answer: "which web maps are using service X?"
#   or "if I retire service X, which maps will break?"
#
# FILE 2: unique_services.csv
#   One row per unique service URL. Your clean service inventory.
#   Use this to answer: "what services exist in my environment?"
#
# SAFE: These files are written to YOUR LOCAL MACHINE ONLY.
#       Nothing is uploaded, published, or sent to any portal.
#       No portal items, services, or configurations are touched.
# =============================================================================

docs = os.path.expanduser("~/Documents")
# ^^^ os.path.expanduser("~") resolves the ~ shorthand to your actual Windows
#     user profile path, e.g. "C:\Users\YourName". Appending "\Documents" gives
#     us the full path to your Documents folder. Using expanduser means this
#     works regardless of what your Windows username actually is.

all_path    = os.path.join(docs, "all_layers.csv")
# ^^^ os.path.join() builds a full file path by combining the folder path and
#     filename with the correct separator for your OS (backslash on Windows).
#     Result example: "C:\Users\YourName\Documents\all_layers.csv"

unique_path = os.path.join(docs, "unique_services.csv")
# ^^^ Same pattern for the second file.
#     Result example: "C:\Users\YourName\Documents\unique_services.csv"


# -- Write the full layer-reference table -------------------------------------

with open(all_path, 'w', newline='', encoding='utf-8') as f:
# ^^^ open() creates (or overwrites) the file at all_path.
#     'w' = write mode (creates the file if it doesn't exist, overwrites if it does).
#     newline='' is required by Python's csv module on Windows to prevent it
#     from writing extra blank lines between every row.
#     encoding='utf-8' ensures layer names with special characters (accents,
#     symbols, etc.) are written correctly.
#     The 'with' statement ensures the file is properly closed and saved even
#     if something goes wrong — no risk of a half-written, corrupted file.

    writer = csv.DictWriter(
    # ^^^ DictWriter lets us write dicts directly as rows. Each key in the dict
    #     maps to a column name we specify in fieldnames below.

        f,
        # ^^^ 'f' is the file object opened by the 'with' statement above.

        fieldnames=['webmap_title', 'webmap_id', 'layer_title', 'layer_type', 'layer_url']
        # ^^^ The column names for the CSV header row, in the order they'll appear.
        #     These must exactly match the keys used in the results dicts in Section 5.
    )
    writer.writeheader()
    # ^^^ Writes the column name row as the first line of the CSV file.
    #     Without this, the CSV would have no header and be hard to read in Excel.

    writer.writerows(results)
    # ^^^ Writes all rows in the results list to the file in one call.
    #     Each dict in results becomes one row, with values placed in the
    #     columns matching their keys. Much faster than looping and writing
    #     one row at a time.


# -- Write the deduplicated unique-services list ------------------------------

with open(unique_path, 'w', newline='', encoding='utf-8') as f:
# ^^^ Same file-opening pattern as above, but for the unique services file.

    writer = csv.writer(f)
    # ^^^ Regular csv.writer (not DictWriter) since we're writing a simple
    #     single-column list rather than a dict with named fields.

    writer.writerow(['service_url'])
    # ^^^ Write the header row — a single column called 'service_url'.
    #     writerow() takes a list; a one-item list gives us a single column.

    for url in unique_urls:
        writer.writerow([url])
        # ^^^ Write one row per unique URL. Again, a one-item list for a
        #     single-column CSV. Square brackets turn the string into a list
        #     as required by writerow().


# -- Final confirmation -------------------------------------------------------

print(f"\nCSVs written to your local Documents folder:")
print(f"  Full layer reference table : {all_path}")
# ^^^ Print the full path so you can navigate to it directly or copy-paste into Explorer.

print(f"  Unique service URLs only   : {unique_path}")

print("\nDone. No portal items were modified.")
# ^^^ Explicit confirmation that the script completed without touching the portal.

#os.startfile(output_path)
# ^^^ Opens the finished CSV file using whatever application Windows has
#     associated with .csv files (typically Microsoft Excel or Notepad).
#     This is a convenience step — comment it out if you don't want the
#     file to open automatically, or if running on a non-Windows machine
#     (os.startfile() is Windows-only; on macOS/Linux use subprocess.call
#     with 'open' or 'xdg-open' respectively).
