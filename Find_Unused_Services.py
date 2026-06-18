# =============================================================================
# FIND UNUSED SERVICES
# =============================================================================
# PURPOSE:
#   Connect to an ArcGIS portal (AGOL or Enterprise) using your active ArcGIS
#   Pro sign-in, inventory every Map Image, Feature, Vector Tile, and Image
#   service in the portal, then cross-reference them against every Web Map to
#   determine which services are NOT referenced by any web map at all.
#   Results are printed to the console and saved as a CSV on your local machine.
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
#     and to search for items. This is the only arcgis module we need in 2.4.x
#     since we're reading raw JSON instead of using the old WebMap class.
 
import csv
# ^^^ Python's built-in CSV module. Used at the end of the script to write
#     results to a .csv file on your local machine. Part of Python's standard
#     library — no installation needed, nothing network-related.
 
import os
# ^^^ Python's built-in operating system interface module. We use it for
#     os.path.expanduser("~") and os.path.join() to build the correct file
#     path to your Documents folder regardless of your Windows username.
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
 
print(f"\nConnected to portal: {gis.properties.portalHostname}")
# ^^^ Print a confirmation of which portal we connected to.
#     gis.properties is a dict-like object of portal metadata (read-only).
#     .portalHostname is the domain name of the portal, e.g. "myorg.maps.arcgis.com"
#     or "enterprise.mycompany.com". This is just for your information —
#     useful to confirm you're pointed at the right environment before a
#     long-running inventory scan.
 
 
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
    #                This comes from the web map's JSON under 'operationalLayers'
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
    #
    #   This function checks the layer type first, then reads the correct key,
    #   so we always get a URL regardless of layer type.
    #   If neither key exists, it returns None so the caller knows no URL
    #   was found and can skip the match attempt for this layer.
    #
    # PARAMETERS:
    #   lyr_dict : a single layer dict from the web map JSON.
    #
    # RETURNS:
    #   A string containing the service URL, or None if none was found.
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
 
        return lyr_dict.get('styleUrl', None)
        # ^^^ Read 'styleUrl' from the dict. If it's missing, return None.
        #     'return' immediately exits the function with this value.
 
    return lyr_dict.get('url', None)
    # ^^^ For all other layer types: read 'url' from the dict.
    #     If 'url' is missing (unusual but possible for some layer types like
    #     annotation layers or unsupported types), return None.
    #     This line is only reached if the layer was NOT a VectorTileLayer.
 
 
# =============================================================================
# SECTION 4 — BUILD THE SERVICE INVENTORY
# =============================================================================
# This section queries the portal for every Map Image, Feature, Vector Tile,
# and Image service item it contains. These are the services we will test
# against web maps to determine which ones are unused.
#
# SAFE: .search() sends a read-only REST API GET request. Nothing is created,
#       modified, or deleted. This is equivalent to running a portal search.
# =============================================================================
 
print("Searching for all services in the portal — this may take a moment...\n")
# ^^^ Simple status message so you know the script is running and not frozen.
#     Large portals with thousands of service items can take 10–30 seconds here.
 
services = (
    gis.content.search(query="", item_type="Map Service",         max_items=10000) +
    gis.content.search(query="", item_type="Feature Service",     max_items=10000) +
    gis.content.search(query="", item_type="Vector Tile Service", max_items=10000) +
    gis.content.search(query="", item_type="Image Service",       max_items=10000)
)
# ^^^ gis.content.search() sends a read-only REST API GET request to the portal's
#     item search endpoint and returns a list of Item objects matching the filter.
#
#     We run four separate searches (one per service type) because the API's
#     item_type filter only accepts a single type per call. The + operators
#     concatenate all four result lists into one combined Python list.
#
#     query=""        : empty string means no title/tag filter — return everything.
#     item_type=...   : filters results to that specific Esri item type only.
#     max_items=10000 : the default cap is 100 items; 10000 raises that ceiling.
#                       If your portal has more than 10,000 of any one type,
#                       raise this value further.
#
#     The four types covered:
#       "Map Service"         — ArcGIS Map Image Services (.MapServer)
#       "Feature Service"     — ArcGIS Feature Services (.FeatureServer)
#       "Vector Tile Service" — Vector Tile packages (.VectorTileServer)
#       "Image Service"       — Raster/Image Services (.ImageServer)
 
print(f"Found {len(services)} service item(s) to check.\n")
# ^^^ Confirm how many service items were found before we start the web map scan.
#     This is useful to sanity-check that the search returned sensible numbers.
 
# Build a lookup dict: service URL -> Item object
# This lets us efficiently match URLs found in web maps back to their Item.
service_lookup = {}
# ^^^ An empty dict we'll populate in the loop below.
#     Keys will be service URLs (strings); values will be the Item objects.
#     Storing it as a dict gives us O(1) lookup performance later when we
#     check whether a web map URL matches any known service.
 
for svc in services:
    # ^^^ Loop over every service Item object in the combined list.
 
    if svc.url:
        # ^^^ Only add the service to the lookup if it actually has a URL.
        #     Some portal items of these types may exist without a live URL
        #     (e.g. unpublished drafts or broken items).
 
        service_lookup[svc.url] = svc
        # ^^^ Store the item keyed by its URL. If two items somehow share the
        #     same URL, the last one wins — this is intentional, as duplicates
        #     would both be marked "used" or "unused" identically.
 
print(f"Built service URL lookup with {len(service_lookup)} unique URL(s).\n")
# ^^^ Confirm the lookup size. A noticeably smaller count than 'services' above
#     means some items had no URL and were skipped — that's normal.
 
 
# =============================================================================
# SECTION 5 — SEARCH ALL WEB MAPS AND COLLECT REFERENCED SERVICE URLS
# =============================================================================
# This section queries the portal for every Web Map, then reads the raw JSON
# of each one to extract all service URLs referenced by its layers.
#
# We collect every URL we find into a Python set called 'used_urls'.
# Any service URL in that set is considered "used" — referenced by at least
# one web map. Any service URL NOT in that set is considered "unused."
#
# SAFE: item.get_data() sends a read-only REST GET request to fetch the item's
#       stored JSON. It is the same underlying data the old WebMap() class used
#       to fetch internally. No writes occur at any point in this section.
# =============================================================================
 
print("Searching for all Web Maps — this may take a moment on large portals...\n")
 
web_maps = gis.content.search(query="", item_type="Web Map", max_items=10000)
# ^^^ Same .search() pattern as Section 4, this time filtering for Web Map items.
#     Web Maps are the primary consumers of services in an ArcGIS organisation —
#     if a service isn't in any web map, it's a strong signal it may be unused.
 
print(f"Found {len(web_maps)} web map(s). Scanning layers...\n")
 
used_urls = set()
# ^^^ A Python set that will accumulate every service URL we encounter across
#     all web maps. Sets automatically deduplicate — adding the same URL a
#     hundred times still results in one entry. This is more efficient than
#     a list for this use case since we only care about presence, not count.
 
for item in web_maps:
    # ^^^ Loop over every Web Map item returned by the search above.
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
 
        # -- Collect basemap layer URLs ----------------------------------------
 
        basemap_layers = data.get('baseMap', {}).get('baseMapLayers', [])
        # ^^^ Read basemap layers from the web map JSON.
        #     Basemaps are stored separately from operational layers under:
        #       data['baseMap']['baseMapLayers']
        #     We include them here because some organisations publish their own
        #     basemap services that would show as unused if we only checked
        #     operational layers.
        #     The chained .get() calls are safe — if either key is missing, we
        #     get an empty list rather than a KeyError.
 
        for bm in basemap_layers:
            # ^^^ Loop over each basemap layer dict.
 
            url = get_layer_url(bm)
            # ^^^ Resolve the URL using our helper function (handles VTS styleUrl).
 
            if url:
                used_urls.add(url)
                # ^^^ add() puts the URL into the set. If it's already there,
                #     nothing changes — sets are automatically deduplicated.
 
        # -- Collect operational layer URLs ------------------------------------
 
        operational_layers = data.get('operationalLayers', [])
        # ^^^ Read the 'operationalLayers' list from the web map JSON.
        #     'operationalLayers' is the standard ArcGIS JSON key for all the
        #     user-added layers in a web map — Feature Layers, Map Services,
        #     WMS layers, etc.
        #     .get('operationalLayers', []) returns an empty list if missing.
 
        flat_layers = unnest_layers(operational_layers)
        # ^^^ Call the function defined in Section 2 to recursively flatten any
        #     group layers and return a single flat list of all leaf layers.
 
        for lyr in flat_layers:
            # ^^^ Loop over every individual (non-group) layer in this web map.
 
            url = get_layer_url(lyr)
            # ^^^ Resolve the URL using the helper function from Section 3.
 
            if url:
                used_urls.add(url)
                # ^^^ Record this URL as "used."
 
    except Exception as e:
        # ^^^ If anything went wrong processing this entire web map, catch the
        #     error, print a message identifying which map failed, and continue
        #     to the next map. One broken map should never abort the whole run.
        print(f"  [error] Could not process web map '{item.title}': {e}")
 
 
# =============================================================================
# SECTION 6 — IDENTIFY UNUSED SERVICES
# =============================================================================
# Now that we have a complete set of every URL referenced by any web map,
# we compare it against our service inventory to find services that were
# never referenced.
#
# A service is considered unused if its URL does not appear in used_urls.
#
# SAFE: Pure Python set and list operations. No network calls whatsoever.
# =============================================================================
 
unused_services = []
# ^^^ An empty list we'll populate with Item objects for services that are
#     not referenced by any web map.
 
for url, svc_item in service_lookup.items():
    # ^^^ Loop over every (url, item) pair in our service lookup dict.
    #     url      : the service's REST endpoint URL string
    #     svc_item : the corresponding portal Item object
 
    if not any(url in used_url for used_url in used_urls):
        # ^^^ Check whether this service URL appears as a substring in ANY
        #     of the URLs collected from web maps.
        #
        #     We use 'in' (substring check) rather than exact equality because
        #     web maps often reference a sub-layer URL like:
        #       https://server.com/arcgis/rest/services/Roads/MapServer/0
        #     while the service item's URL is:
        #       https://server.com/arcgis/rest/services/Roads/MapServer
        #     A strict == would miss this match. Checking whether the service
        #     URL is a substring of the web map URL handles this correctly.
        #
        #     any(...) short-circuits: it stops checking as soon as one match
        #     is found, so it's efficient even with large used_urls sets.
 
        unused_services.append(svc_item)
        # ^^^ This service URL was not found in any web map — mark it unused.
 
unused_services.sort(key=lambda s: s.title.lower())
# ^^^ Sort the unused services list alphabetically by title (case-insensitive)
#     so the output is easy to scan. lambda s: s.title.lower() is a small
#     inline function that extracts the lowercased title from each Item object
#     for comparison purposes only — it does not change the items themselves.
 
 
# =============================================================================
# SECTION 7 — PRINT SUMMARY TO CONSOLE
# =============================================================================
# Prints results to the Python window / notebook output.
# SAFE: print() only — no side effects of any kind.
# =============================================================================
 
portal_home = f"https://{gis.properties.portalHostname}/home/item.html?id="
# ^^^ Build the base URL for direct portal item links.
#     Appending a service item's ID to this string gives a clickable URL that
#     opens that item's detail page in the portal. Useful for quick navigation.
 
print(f"\n{'='*60}")
print(f"TOTAL SERVICES SCANNED : {len(service_lookup)}")
# ^^^ How many unique service URLs were found across all four service types.
 
print(f"WEB MAPS SCANNED       : {len(web_maps)}")
# ^^^ How many web maps were checked during the scan.
 
print(f"UNUSED SERVICES FOUND  : {len(unused_services)}")
# ^^^ The headline number — how many services are not referenced by any web map.
 
print(f"{'='*60}\n")
 
if unused_services:
    print("The following services are not used in any web map:\n")
    for svc in unused_services:
        print(f"  {svc.title}")
        print(f"    Type  : {svc.type}")
        print(f"    URL   : {svc.url}")
        print(f"    Portal: {portal_home}{svc.id}\n")
        # ^^^ Print the item title, service type, REST endpoint URL, and a
        #     direct link to the item's portal page for each unused service.
else:
    print("No unused services found — every service is referenced by at least one web map.")
    # ^^^ Handle the (hopefully common) case where nothing is unused.
 
 
# =============================================================================
# SECTION 8 — EXPORT RESULTS TO CSV ON YOUR LOCAL MACHINE
# =============================================================================
# Writes one CSV file to your Windows Documents folder listing all unused
# services with their title, type, REST URL, and direct portal link.
#
# SAFE: This file is written to YOUR LOCAL MACHINE ONLY.
#       Nothing is uploaded, published, or sent to any portal.
#       No portal items, services, or configurations are touched.
# =============================================================================
 
docs = os.path.expanduser("~/Documents")
# ^^^ os.path.expanduser("~") resolves the ~ shorthand to your actual Windows
#     user profile path, e.g. "C:\Users\YourName". Appending "\Documents"
#     gives us the full path to your Documents folder. Using expanduser means
#     this works regardless of what your Windows username actually is.
 
output_path = os.path.join(docs, "unused_services.csv")
# ^^^ os.path.join() builds a full file path by combining the folder path
#     and filename with the correct separator for your OS (backslash on Windows).
#     Result example: "C:\Users\YourName\Documents\unused_services.csv"
 
with open(output_path, 'w', newline='', encoding='utf-8') as f:
# ^^^ open() creates (or overwrites) the file at output_path.
#     'w'              : write mode — creates the file if it doesn't exist,
#                        overwrites it if it does.
#     newline=''       : required by Python's csv module on Windows to prevent
#                        it from writing extra blank lines between every row.
#     encoding='utf-8' : ensures service names with special characters (accents,
#                        symbols, etc.) are written correctly.
#     The 'with' statement ensures the file is properly closed and saved even
#     if something goes wrong — no risk of a half-written, corrupted file.
 
    writer = csv.DictWriter(
    # ^^^ DictWriter lets us write dicts directly as rows. Each key in the dict
    #     maps to a column name we specify in fieldnames below.
 
        f,
        # ^^^ 'f' is the file object opened by the 'with' statement above.
 
        fieldnames=['title', 'type', 'service_url', 'portal_link']
        # ^^^ The column names for the CSV header row, in the order they'll appear.
        #     These must exactly match the keys used in the row dicts written below.
    )
    writer.writeheader()
    # ^^^ Writes the column name row as the first line of the CSV file.
    #     Without this, the CSV would have no header and be hard to read in Excel.
 
    for svc in unused_services:
        writer.writerow({
            'title':       svc.title,
            # ^^^ The display name of the service item in the portal.
 
            'type':        svc.type,
            # ^^^ The Esri item type string, e.g. "Feature Service", "Map Service".
 
            'service_url': svc.url,
            # ^^^ The REST endpoint URL of the service.
 
            'portal_link': f"{portal_home}{svc.id}"
            # ^^^ Direct URL to this item's page in the portal.
            #     Built by combining the base portal home URL with the item's GUID.
        })
        # ^^^ Write one row per unused service.
 
 
# -- Final confirmation -------------------------------------------------------
 
print(f"\nCSV written to your local Documents folder:")
print(f"  Unused services list: {output_path}")
# ^^^ Print the full path so you can navigate to it directly or copy-paste
#     into Windows Explorer.
 
print("\nDone. No portal items were modified.")
# ^^^ Explicit confirmation that the script completed without touching the portal.

#os.startfile(output_path)
# ^^^ Opens the finished CSV file using whatever application Windows has
#     associated with .csv files (typically Microsoft Excel or Notepad).
#     This is a convenience step — comment it out if you don't want the
#     file to open automatically, or if running on a non-Windows machine
#     (os.startfile() is Windows-only; on macOS/Linux use subprocess.call
#     with 'open' or 'xdg-open' respectively).