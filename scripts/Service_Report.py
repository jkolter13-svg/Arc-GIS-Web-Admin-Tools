# =============================================================================
# SERVICE INVENTORY SCRIPT
# =============================================================================
# PURPOSE:
#   Connect to an ArcGIS portal (AGOL or Enterprise) using your active ArcGIS
#   Pro sign-in, scan every Map Image, Feature, Vector Tile, and Image service
#   in that portal, and write a CSV file containing each service's title, type,
#   layers, URL, sharing level, groups it's shared with, and other useful
#   metadata for auditing your service catalogue.
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
#   Optionally adjust OUTPUT_FILE_PATH in Section 2 before running.
#
# REQUIREMENTS:
#   ArcGIS API for Python 2.4.x (ships with ArcGIS Pro 3.x)
#
# CREDITS:
#   Original code by (C) 2019 Joshua Sharp-Heward, Whangarei, New Zealand
#   Released under GNU Lesser Public License v3.0 (GPLv3)
#   email jsh726@uowmail.edu.au
#   linkedin https://www.linkedin.com/in/joshua-sharp-heward-89b129131/
#   Modified, Updated, and Commented By: Jonathan Kolterman
#   email jkolterman13@gmail.com
#   linkedin https://www.linkedin.com/in/jonathan-kolterman-1808342b8
# =============================================================================
 
 
# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------
 
from arcgis.gis import GIS
# ^^^ Loads the GIS class from Esri's ArcGIS API for Python.
#     GIS is the main entry point for connecting to AGOL or Enterprise.
 
import csv
# ^^^ Python's built-in CSV module for writing the output file.
 
import os
# ^^^ Used for building the output file path and opening the file on completion.
 
 
# =============================================================================
# SECTION 1 — PORTAL CONNECTION
# =============================================================================
 
gis = GIS('pro')
# ^^^ Connects using the portal already active in ArcGIS Pro — no credentials
#     stored in this script.
#
#     ALTERNATIVES:
#       gis = GIS('home')                                → ArcGIS Notebook inside portal
#       gis = GIS("https://your-enterprise.com/portal")  → explicit Enterprise URL
 
print(f"\nConnected to portal : {gis.properties.portalHostname}")
print(f"Signed in as        : {gis.properties['user']['username']}\n")
# ^^^ Confirm which portal we connected to and who we're signed in as before
#     starting a potentially long-running scan.
 
 
# =============================================================================
# SECTION 2 — CONFIGURATION
# =============================================================================
 
OUTPUT_FILE_PATH = os.path.join(os.path.expanduser("~/Documents"), "service_inventory.csv")
# ^^^ Where to save the CSV on your local machine.
#     Defaults to your Windows Documents folder. To change it, replace this
#     line with a raw string path, e.g.:
#       OUTPUT_FILE_PATH = r"C:\GIS\Reports\service_inventory.csv"
 
GET_LAYERS = True
# ^^^ Set to False to skip reading each service's layer list.
#     Reading .layers makes a live REST call to the service endpoint itself
#     (not just the portal), which can be slow or time out for services that
#     are offline, broken, or behind a firewall the script can't reach.
#     When False, 'service_layers' will be blank for every service and the
#     scan will run much faster on large portals with many services.
 
 
# =============================================================================
# SECTION 3 — HELPER: SAFE PROPERTY READER
# =============================================================================
 
def safe_get(item, key, default=""):
    # -------------------------------------------------------------------------
    # WHAT THIS FUNCTION DOES:
    #   ArcGIS API Item objects behave like a hybrid — some properties are
    #   Python attributes (item.title) and some are dict-style keys backed by
    #   the raw JSON the portal returned (item['snippet']). When a key is
    #   absent from the portal's JSON response, accessing it either raises a
    #   KeyError (dict-style) or returns None (attribute-style), depending on
    #   which path you use and which API version you're on.
    #
    #   This function tries both access patterns and returns 'default' (empty
    #   string) for anything that is missing, None, or raises any error at all.
    #   This means a missing or unsupported field always produces a blank CSV
    #   cell rather than crashing the script.
    #
    # PARAMETERS:
    #   item    : the Item object from gis.content.search()
    #   key     : string name of the property to read
    #   default : value to return when the property is unavailable (default "")
    #
    # RETURNS:
    #   The property value as returned by the API, or default.
    # -------------------------------------------------------------------------
 
    try:
        value = getattr(item, key, None)
        # ^^^ Try attribute-style access first (e.g. item.title).
        #     getattr returns None if the attribute doesn't exist.
 
        if value is None:
            value = item[key]
            # ^^^ Fall back to dict-style access (e.g. item['snippet']).
            #     This can raise KeyError, which is caught below.
 
        if value is None:
            return default
            # ^^^ The key existed but its value was None — treat as not set.
 
        return value
 
    except Exception:
        # ^^^ Any error (KeyError, AttributeError, TypeError, etc.) means the
        #     property is simply not available for this item. Return default
        #     silently so one missing field never crashes the whole row.
        return default
 
 
# =============================================================================
# SECTION 4 — SEARCH FOR ALL SERVICES
# =============================================================================
# This section queries the portal for every Map Image, Feature, Vector Tile,
# and Image service item it contains.
#
# SAFE: .search() sends a read-only REST API GET request. Nothing is created,
#       modified, or deleted. This is equivalent to running a portal search.
# =============================================================================
 
print("Searching for all services in the portal — this may take a moment...\n")
 
services = (
    gis.content.search(query="", item_type="Map Service",         max_items=10000) +
    gis.content.search(query="", item_type="Feature Service",     max_items=10000) +
    gis.content.search(query="", item_type="Vector Tile Service", max_items=10000) +
    gis.content.search(query="", item_type="Image Service",       max_items=10000)
)
# ^^^ Four separate searches (one per service type) concatenated into one list,
#     since item_type only accepts a single type per call.
#     max_items=10000 raises the default cap of 100 to avoid silent truncation.
#
#     The four types covered:
#       "Map Service"         — ArcGIS Map Image Services (.MapServer)
#       "Feature Service"     — ArcGIS Feature Services (.FeatureServer)
#       "Vector Tile Service" — Vector Tile packages (.VectorTileServer)
#       "Image Service"       — Raster/Image Services (.ImageServer)
 
print(f"Found {len(services)} service(s). Collecting properties...\n")
 
 
# =============================================================================
# SECTION 5 — BUILD THE SERVICE DATA COLLECTION
# =============================================================================
# Loops over every service item and collects available properties into a list
# of dicts. One dict per service; one key per CSV column.
#
# COLUMNS COLLECTED:
#
#   IDENTITY
#     service_name    — display title of the item in the portal
#     service_type    — Esri item type (e.g. "Feature Service")
#     service_id      — unique 32-character item GUID
#     service_url     — REST endpoint URL of the service
#     owner           — username of the item's owner
#     created         — date the item was created in the portal
#     last_modified   — date the item was last updated
#
#   LAYERS
#     service_layers  — comma-separated list of sub-layer names (Group Layers
#                        excluded). "No layers" if the layer list could not be
#                        read (offline service, no .layers property, etc.).
#                        Blank if GET_LAYERS is set to False.
#     layer_count     — number of layers listed in service_layers, or blank
#                        if GET_LAYERS is False or the layer list errored.
#
#   SHARING
#     sharing         — access level: "PRIVATE", "ORG", "PUBLIC", or "SHARED"
#     shared_groups   — comma-separated list of group titles this item is
#                        shared with. "Not shared to groups" if none.
#
#   USAGE
#     summary         — short description / snippet text (if set)
#     tags            — comma-separated list of tags on the item
#     num_views       — number of times the item has been viewed in the portal
#
# NOTE: Fields may be blank for non-admin scans, items the signed-in user
#       cannot fully access, or services that are currently offline.
# =============================================================================
 
service_rows = []
# ^^^ Accumulates one dict per successfully processed service.
 
for i, service in enumerate(services, start=1):
    # ^^^ enumerate gives us a counter 'i' so we can print progress.
    #     'service' is the current Item object from the combined search list.
 
    try:
        print(f"  Processing {i}/{len(services)}: {service.title}")
 
        # -- Layers -------------------------------------------------------------
 
        layers = []
        # ^^^ Empty list to accumulate sub-layer names for this service.
 
        if GET_LAYERS:
            # ^^^ Only attempt to read layers if the GET_LAYERS toggle is True.
            #     Reading .layers makes a live call to the service's REST
            #     endpoint, separate from the portal item search above.
 
            try:
                for layer in service.layers:
                    # ^^^ service.layers fetches the service's layer list by
                    #     calling its REST endpoint directly (e.g. .../MapServer
                    #     or .../FeatureServer), not the portal item search.
                    #     This can fail if the service is offline, the layer
                    #     definition is malformed, or the URL is unreachable.
 
                    if layer.properties['type'] != 'Group Layer':
                        # ^^^ Group Layers are organisational containers, not
                        #     real data layers — exclude them from the list so
                        #     it only contains actual feature/raster layers.
 
                        layers.append(layer.properties['name'])
                        # ^^^ .properties['name'] is the layer's name as defined
                        #     in the service (may differ from its display title
                        #     in any individual web map).
 
            except Exception:
                layers.append("No layers")
                # ^^^ Could not read the layer list — service may be offline,
                #     a Vector Tile Service (which has no .layers in the same
                #     sense), or otherwise unreadable. Use a placeholder so the
                #     CSV cell isn't blank and ambiguous with "0 layers found".
 
        layers_str = ", ".join(layers)
        layer_count = len(layers) if (GET_LAYERS and layers != ["No layers"]) else ""
        # ^^^ Numeric layer count column. Blank if GET_LAYERS is False or if
        #     the layer read failed (placeholder "No layers" present).
 
        # -- Sharing / groups -----------------------------------------------------
 
        groups = []
        # ^^^ Empty list to accumulate group titles this item is shared with.
 
        try:
            shared_groups = service.shared_with.get('groups', [])
            # ^^^ service.shared_with returns a dict like:
            #       {'everyone': bool, 'org': bool, 'groups': [Group, ...]}
            #     .get('groups', []) safely returns an empty list if the key
            #     is missing for any reason.
 
            if shared_groups:
                for group in shared_groups:
                    try:
                        groups.append(group.title)
                    except Exception:
                        groups.append("External private group")
                        # ^^^ Same pattern as the user inventory script —
                        #     external/secured groups can raise when their
                        #     title is read by a user without visibility.
            else:
                groups.append("Not shared to groups")
 
        except Exception:
            groups.append("Not shared to groups")
            # ^^^ If shared_with itself couldn't be read at all, fall back to
            #     the same placeholder rather than leaving the cell blank.
 
        groups_str = ", ".join(groups)
 
        # -- Tags -----------------------------------------------------------------
 
        tags = safe_get(service, 'tags', [])
        tags_str = ", ".join(tags) if tags else ""
        # ^^^ service.tags is a list of tag strings set on the item.
        #     Joined into one comma-separated cell for the CSV.
 
        # -- Build the row dict -----------------------------------------------
 
        service_rows.append({
 
            # IDENTITY
            'service_name':   safe_get(service, 'title'),
            'service_type':   safe_get(service, 'type'),
            'service_id':     safe_get(service, 'id'),
            'service_url':    safe_get(service, 'url'),
            'owner':          safe_get(service, 'owner'),
            'created':        safe_get(service, 'created'),
            'last_modified':  safe_get(service, 'modified'),
 
            # LAYERS
            'service_layers': layers_str,
            'layer_count':    layer_count,
 
            # SHARING
            'sharing':        safe_get(service, 'access'),
            'shared_groups':  groups_str,
 
            # USAGE
            'summary':        safe_get(service, 'snippet'),
            'tags':           tags_str,
            'num_views':      safe_get(service, 'numViews'),
        })
 
    except Exception as e:
        print(f"  [warn] Could not process service '{getattr(service, 'title', '?')}': {e}")
        # ^^^ If anything unexpected fails at the outer level for this service,
        #     log it and move on. The service is skipped from the CSV rather
        #     than crashing the entire run.
 
print(f"\nCollected data for {len(service_rows)} service(s). Writing CSV...\n")
 
 
# =============================================================================
# SECTION 6 — WRITE RESULTS TO CSV ON YOUR LOCAL MACHINE
# =============================================================================
# Writes one CSV file to the path set in OUTPUT_FILE_PATH in Section 2.
# One row per service, with all columns listed in SECTION 5 above.
#
# SAFE: This file is written to YOUR LOCAL MACHINE ONLY.
#       Nothing is uploaded, published, or sent to any portal.
#       No portal items, services, or configurations are touched.
# =============================================================================
 
FIELD_NAMES = [
    'service_name', 'service_type', 'service_id', 'service_url', 'owner',
    'created', 'last_modified',
    'service_layers', 'layer_count',
    'sharing', 'shared_groups',
    'summary', 'tags', 'num_views',
]
# ^^^ Column names for the CSV header row, in display order.
#     Must match the keys used in the dicts appended to service_rows.
 
with open(OUTPUT_FILE_PATH, mode='w', newline='', encoding='utf-8') as f:
# ^^^ 'w' creates or overwrites the file. newline='' prevents Windows double-spacing.
#     encoding='utf-8' handles special characters in titles/summaries correctly.
 
    writer = csv.DictWriter(f, fieldnames=FIELD_NAMES, extrasaction='ignore')
    # ^^^ extrasaction='ignore' silently drops any unexpected keys rather than
    #     raising a ValueError — a safety net against API response changes.
 
    writer.writeheader()
    # ^^^ Writes the column name row as the first line of the CSV.
 
    writer.writerows(service_rows)
    # ^^^ Writes all collected rows in one call.
 
 
# =============================================================================
# SECTION 7 — CONFIRMATION AND OPEN FILE
# =============================================================================
 
print(f"CSV written to  : {OUTPUT_FILE_PATH}")
print(f"Services exported : {len(service_rows)}")
print("\nDone. No portal items were modified.")
# ^^^ Explicit confirmation that the script completed without touching the portal.
 
#os.startfile(OUTPUT_FILE_PATH)
# ^^^ Opens the CSV in Excel (or your default .csv application) automatically.
#     Comment this line out if running on macOS/Linux — os.startfile() is
#     Windows-only. On macOS use: subprocess.call(['open', OUTPUT_FILE_PATH])
