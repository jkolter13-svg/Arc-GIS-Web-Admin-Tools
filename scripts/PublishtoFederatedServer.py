# =============================================================================
# publish_to_federated_server.py
#
# Publishes a map from ArcGIS Pro to a federated ArcGIS Server (10.9.1) as a
# Map Image Service & Feature service with editing enabled, referencing a registered
# Enterprise GDB data source (no data copy).
#
# After publishing:
#   - Deletes the .sd upload item (staging artifact, safe to remove)
#   - Moves Map Service and Feature Service items to PORTAL_FOLDER
#   - Enables delete protection on those items so they can't be accidentally
#     removed from Portal (which would take the server service down with them)
#
# Requirements:
#   - ArcGIS Pro 2.9
#   - ArcGIS Enterprise / Server 10.9.1 (federated)
#   - Active Pro session with Portal admin credentials (GIS("pro"))
#   - Map layers must point to a data source already registered with the server
#   - Account must have Portal Administrator role
#
# WHY USE THIS SCRIPT INSTEAD OF THE BUILT-IN ARCGIS PRO SHARING WIZARD?
#
#   ArcGIS Pro has a built-in "Share as Web Layer" GUI (right-click a map →
#   Share → Web Layer).  That wizard works fine for one-off publishing, but
#   it has a number of limitations that this script addresses:
#
#   1. NO FEATURE ACCESS TOGGLE FOR FEDERATED SERVERS
#      When publishing to a federated ArcGIS Server (as opposed to ArcGIS
#      Online), the Share wizard does not expose a checkbox to enable Feature
#      Access / FeatureServer.  The only supported path is to manually edit
#      the .sddraft XML after exporting it exactly what Step 4 does.
#      Without this script you would have to export the draft, edit the XML
#      by hand every single time, then re-stage and publish yourself.
#
#   2. NO AUTOMATIC CLEANUP OF THE .sd STAGING ITEM
#      The wizard uploads the compiled .sd file to Portal and leaves it
#      there.  Over time this clutters your content library with
#      stale "Service Definition" items that serve no purpose once the service
#      is live. This script records the .sd item ID before publishing and
#      deletes it automatically in Step 8.
#
#   3. NO DELETE-PROTECTION
#      The wizard provides no way to enable delete-protection on the items it
#      creates.  That means anyone with edit access to the Portal content
#      library can accidentally delete a live service item and immediately
#      take the server service offline.  Step 8 protects every service item
#      as part of the standard publish workflow.
#
#   4. REPEATABILITY AND CONSISTENCY
#      Every setting: server URL, folder names, capabilities, tags, lives
#      in the CONFIGURATION block at the top.  Re-publishing after a data
#      update or re-deploying to a new environment is a single config edit
#      followed by a full run.  With the wizard, every setting must be
#      manually re-entered in the GUI each time, which introduces human error.
#
#   WHEN THE WIZARD IS STILL FINE:
#      If you're doing a quick one-off publish to ArcGIS Online (not a
#      federated server), don't need Feature Access, and aren't worried about
#      folder organization or protection, the built-in wizard is perfectly
#      adequate.  This script exists for the repeatable, federated-server,
#      Feature-Access-enabled workflow.
#
# Run from an ArcGIS Pro Notebook.
#
# CREDITS:
#   Jonathan Kolterman 2026
#   email jkolterman13@gmail.com
#   linkedin https://www.linkedin.com/in/jonathan-kolterman-1808342b8
# =============================================================================

import os           # File path manipulation and existence checks
import time         # Used for the post-publish sleep (lets Portal settle)
import arcpy        # ArcGIS geoprocessing — staging and publishing the service
import xml.dom.minidom as DOM   # Parses and edits the .sddraft XML to enable Feature Access
from arcgis.gis import GIS      # ArcGIS API for Python — manages Portal items


# =============================================================================
# CONFIGURATION — edit these values before running
# =============================================================================
# All of the "knobs" for this script live here so you don't have to hunt
# through the code every time you want to publish a different service.

APRX_PATH = r"C:\ "
# Full path to the ArcGIS Pro project (.aprx) file that contains the map
# you want to publish.

MAP_NAME = "Map"
# The exact name of the map inside the .aprx to publish.
# Must match what you see in the Contents pane / project panel in ArcGIS Pro.

SERVICE_NAME = ""
# What the service will be called on ArcGIS Server and in Portal.
# Avoid spaces — underscores are conventional.

SERVER_URL = "https://"
# The base REST URL of the federated ArcGIS Server.
# Do NOT include a trailing slash.

SD_FOLDER = r"C:\Scratch"
# Local directory where the temporary .sddraft and .sd files will be written
# during staging.  Must already exist on disk.

SERVER_FOLDER = ""
# Folder on ArcGIS Server where the service will be placed.
# Set to "" (empty string) to publish to the server root.

PORTAL_FOLDER = ""
# Portal content folder where the Map Service and Feature Service items
# will be moved after publishing.
# If it doesn't exist, the script will create it automatically.

SERVICE_SUMMARY = "Published via automated script"
# Short description that appears in Portal and the REST endpoint metadata.

SERVICE_TAGS = "automated, feature service, map service"
# Comma-separated tags applied to the Portal items for search/organization.


# =============================================================================
# DERIVED PATHS  (computed from the config above — don't edit these)
# =============================================================================
# These are built once here rather than scattered through the code so that
# changing SERVICE_NAME or SD_FOLDER above automatically updates everything.

sddraft_path = os.path.join(SD_FOLDER, SERVICE_NAME + ".sddraft")
# e.g. D:\Scratch\TEST.sddraft
# This XML file is the blueprint for the service before it's compiled.

sd_path = os.path.join(SD_FOLDER, SERVICE_NAME + ".sd")
# e.g. D:\Scratch\TEST.sd
# The compiled, binary service definition that gets uploaded to Portal.

# Build the path-within-the-server string for REST URL construction.
# If SERVER_FOLDER is set, services live at: /rest/services/FOLDER/NAME/...
# If SERVER_FOLDER is empty, they live at:   /rest/services/NAME/...
service_folder_path = f"{SERVER_FOLDER}/{SERVICE_NAME}" if SERVER_FOLDER else SERVICE_NAME

map_server_url     = f"{SERVER_URL}/rest/services/{service_folder_path}/MapServer"
# The REST URL where the MapServer endpoint will be accessible after publish.

feature_server_url = f"{SERVER_URL}/rest/services/{service_folder_path}/FeatureServer"
# The REST URL where the FeatureServer endpoint will be accessible after publish.


# =============================================================================
# STEP 1 — Connect to Portal via active ArcGIS Pro session
# =============================================================================
# GIS("pro") is a special shortcut that borrows the Portal connection already
# open in ArcGIS Pro rather than asking for a username/password.  This means:
#   a) No credentials are stored in this script.
#   b) You MUST be signed into Portal in ArcGIS Pro before running this.
#   c) The account must have Portal Administrator role.

print("=" * 60)
print("STEP 1: Connecting to Portal via ArcGIS Pro session...")
print("=" * 60)

gis      = GIS("pro")                       # Borrow the active Pro session
username = gis.properties.user.username     # Grab the signed-in username; used
                                            # later to search for Portal items
                                            # owned by this account

print(f"  Connected as: {username}")
print(f"  Portal:       {gis.url}")


# =============================================================================
# STEP 2 — Open the ArcGIS Pro project and locate the map
# =============================================================================
# arcpy.mp.ArcGISProject opens the .aprx file so we can get a reference to
# the specific map we want to publish.  listMaps() supports wildcard patterns
# but here we pass the exact name to be unambiguous.

print("\n" + "=" * 60)
print("STEP 2: Opening project and locating map...")
print("=" * 60)

aprx = arcpy.mp.ArcGISProject(APRX_PATH)
maps = aprx.listMaps(MAP_NAME)   # Returns a list; empty if name not found

if not maps:
    # Fail loudly with a helpful message that shows what maps DO exist in the
    # project makes typos easy to catch.
    raise ValueError(
        f"Map '{MAP_NAME}' not found in '{APRX_PATH}'.\n"
        f"Available maps: {[m.name for m in aprx.listMaps()]}"
    )

m = maps[0]   # Take the first (and presumably only) match
print(f"  Found map: '{m.name}' with {len(m.listLayers())} layer(s)")


# =============================================================================
# STEP 3 — Create .sddraft targeting the federated server
# =============================================================================
# getWebLayerSharingDraft() builds a SharingDraft object — essentially a
# settings container that knows how to write itself out as a .sddraft XML file.
#
# Key parameters explained:
#   server_type  = "FEDERATED_SERVER"
#       Tells ArcGIS Pro we're publishing to a server that is federated with
#       the Portal we're signed into, rather than a standalone Server or
#       ArcGIS Online.
#
#   service_type = "MAP_IMAGE"
#       We want a Map Image Service (tiles + dynamic maps).  Feature Access
#       is an *extension* of Map Image — we enable it in Step 4 by editing
#       the XML.  You can't request Feature Service directly here.
#
#   copyDataToServer = False
#       CRITICAL: don't bundle a copy of the data into the .sd file.  Instead,
#       the server will use the registered Enterprise GDB connection.  This
#       requires the data source path to already be registered with the server
#       in ArcGIS Server Manager (Server > Site > Data Stores).
#
#   federatedServerUrl = SERVER_URL
#       Which federated server to target.  Must match the server URL as
#       registered in Portal (Admin > Organization > Servers).
#
#   portalFolder = PORTAL_FOLDER
#       Where in Portal's content tree to place the .sd item we'll upload in
#       Step 6.  Note: UploadServiceDefinition (Step 7) IGNORES this for the
#       Map/Feature Service items it creates — we fix that in Step 8.

print("\n" + "=" * 60)
print("STEP 3: Creating .sddraft...")
print("=" * 60)

sddraft = m.getWebLayerSharingDraft(
    server_type  = "FEDERATED_SERVER",
    service_type = "MAP_IMAGE",
    service_name = SERVICE_NAME,
)

sddraft.federatedServerUrl = SERVER_URL
sddraft.copyDataToServer   = False          # Reference registered data; don't embed a copy
sddraft.summary            = SERVICE_SUMMARY
sddraft.tags               = SERVICE_TAGS
sddraft.portalFolder       = PORTAL_FOLDER

sddraft.exportToSDDraft(sddraft_path)       # Write the XML blueprint to disk
print(f"  SDDraft written to: {sddraft_path}")


# =============================================================================
# STEP 4 — Enable Feature Access in .sddraft XML
# =============================================================================
# The .sddraft is a plain XML file.  By default, only Map Image capabilities
# are enabled.  To also expose a FeatureServer endpoint (which clients like
# Field Maps and Survey123 need for editing), we must:
#
#   1. Find the <TypeName>FeatureServer</TypeName> node.
#   2. Set its parent's <Enabled> child to "true".
#   3. Set the WebCapabilities property to include all editing operations.
#
# Why do this in XML rather than in the SharingDraft API?
#   The Python SharingDraft object doesn't expose Feature Access as a property,
#   so raw XML manipulation is the officially documented approach.
#
# WebCapabilities options:
#   Query    — clients can query features (read)
#   Create   — clients can add new features
#   Update   — clients can edit existing features
#   Delete   — clients can remove features
#   Uploads  — clients can attach files
#   Editing  — master switch required alongside Create/Update/Delete

print("\n" + "=" * 60)
print("STEP 4: Enabling Feature Access in .sddraft XML...")
print("=" * 60)

doc = DOM.parse(sddraft_path)               # Parse the entire XML into a DOM tree
feature_extension_found = False             # Sentinel so we can warn if the node is missing

# Walk every <TypeName> element in the document looking for the FeatureServer extension.
for type_name_node in doc.getElementsByTagName("TypeName"):
    if type_name_node.firstChild and type_name_node.firstChild.data == "FeatureServer":
        feature_extension_found = True
        extension_node = type_name_node.parentNode   # <Extension> element that wraps this block

        # Toggle <Enabled> to "true" so ArcGIS Server activates the FeatureServer endpoint.
        for child in extension_node.childNodes:
            if child.nodeName == "Enabled":
                child.firstChild.data = "true"
                print("  FeatureServer Enabled = true")

        # Update the WebCapabilities property inside the extension's PropertyArray.
        # This controls which HTTP verbs/operations the FeatureServer accepts.
        for prop_array in extension_node.getElementsByTagName("PropertyArray"):
            for prop in prop_array.getElementsByTagName("PropertySetProperty"):
                keys = prop.getElementsByTagName("Key")
                vals = prop.getElementsByTagName("Value")
                if keys and keys[0].firstChild and keys[0].firstChild.data == "WebCapabilities":
                    if vals:
                        vals[0].firstChild.data = "Query,Create,Update,Delete,Uploads,Editing"
                        print("  WebCapabilities: Query,Create,Update,Delete,Uploads,Editing")
        break   # Found what we needed; stop iterating

if not feature_extension_found:
    # The XML structure can differ between ArcGIS Pro versions.  If we didn't
    # find the node, Feature Access won't be on — warn rather than silently fail.
    print("  WARNING: FeatureServer node not found — Feature Access may not be enabled.")

# Write the modified XML back to the same .sddraft file.
# StageService (Step 5) reads this file, so the edits must be saved first.
with open(sddraft_path, "w", encoding="utf-8") as f:
    doc.writexml(f)
print("  Modified .sddraft saved.")


# =============================================================================
# STEP 5 — Stage .sddraft → .sd
# =============================================================================
# arcpy.server.StageService compiles the XML .sddraft blueprint into a binary
# .sd (Service Definition) file.  The .sd bundles all service configuration
# and — when copyDataToServer=True — would also include the data.  Here it's
# just configuration since we're referencing registered data.
#
# Staging catches most configuration errors (bad layer sources, missing
# registered data paths, etc.) before we attempt to publish, which makes
# failures much easier to diagnose.
#
# If an .sd already exists at the target path from a previous run, we remove
# it first because StageService won't overwrite an existing file.

print("\n" + "=" * 60)
print("STEP 5: Staging service definition...")
print("=" * 60)

if os.path.exists(sd_path):
    os.remove(sd_path)
    print(f"  Removed existing .sd: {sd_path}")

arcpy.server.StageService(sddraft_path, sd_path)

# Staging warnings (severity 1) are non-fatal but worth logging.
# Common warnings include things like unsupported layer types or projection
# mismatches that won't prevent publishing but may affect functionality.
warnings = arcpy.GetMessages(1)
if warnings:
    print(f"  Staging warnings:\n{warnings}")
print(f"  Staged: {sd_path}")


# =============================================================================
# STEP 6 — Upload .sd to Portal and record its item ID immediately
# =============================================================================
# UploadServiceDefinition (Step 7) needs the .sd to exist in Portal before
# it can publish.  We upload it here separately rather than letting
# UploadServiceDefinition handle it internally because:
#
#   a) It gives us the item ID (SD_ITEM_ID) before the publish step runs.
#      If we waited until after, we'd have to guess which new Portal item is
#      the .sd vs the Map/Feature Service items.
#   b) It lets us put the .sd into PORTAL_FOLDER from the start.
#
# gis.content.add() uploads a file to Portal and returns a ContentItem object.
# The .id property is the Portal GUID for the item — we save it to SD_ITEM_ID
# so Step 8 can find and delete it without any ambiguity.

print("\n" + "=" * 60)
print("STEP 6: Uploading .sd to Portal...")
print("=" * 60)

sd_item = gis.content.add(
    item_properties={
        "title": SERVICE_NAME,          # Human-readable name in Portal
        "type" : "Service Definition",  # Portal item type — must be exact string
        "tags" : SERVICE_TAGS,
    },
    data   = sd_path,       # Path to the local .sd file to upload
    folder = PORTAL_FOLDER, # Portal folder to place the item in
)
SD_ITEM_ID = sd_item.id     # Save the GUID now — we'll use it in Step 8 to delete this item
print(f"  .sd uploaded — Item ID: {SD_ITEM_ID}")


# =============================================================================
# STEP 7 — Publish to federated server
#           Snapshot item IDs before/after to catch everything Portal creates
# =============================================================================
# UploadServiceDefinition does several things in one call:
#   1. Reads the .sd from Portal.
#   2. Sends it to the federated ArcGIS Server.
#   3. ArcGIS Server registers and starts the service.
#   4. Portal automatically creates new content items for the Map Service
#      and (because we enabled it) the Feature Service.
#
# The "before/after snapshot" pattern:
#   We collect all item IDs owned by this user before publishing, then again
#   8 seconds after.  The difference = items created by UploadServiceDefinition.
#   This is more reliable than searching by title or type because Portal's
#   auto-created item titles can vary.
#
# UploadServiceDefinition parameters:
#   in_sd_file      — the local .sd path (arcpy also accepts the Portal item)
#   in_server       — which server to publish to (must be federated)
#   in_service_name — service name on the server
#   in_cluster      — server cluster (empty = default cluster)
#   in_folder_type  — "EXISTING" to place in an existing server folder,
#                     "ROOT" if SERVER_FOLDER is empty
#   in_folder       — the server folder name (or empty for root)
#   in_startupType  — "STARTED" starts the service immediately after publish
#   in_my_contents  — "NO_SHARE_ONLINE" keeps items private (not on ArcGIS Online)
#   in_public       — "PRIVATE" — only the owner and admins can see the service
#   in_organization — "NO_SHARE_ORGANIZATION" — not shared with org members
#   in_groups       — None — not shared with any Portal groups

print("\n" + "=" * 60)
print("STEP 7: Publishing to federated server...")
print("=" * 60)

# Snapshot of all Portal items owned by this account before publishing.
pre_publish_ids = {
    item.id
    for item in gis.content.search(query=f"owner:{username}", max_items=500)
}

arcpy.server.UploadServiceDefinition(
    in_sd_file      = sd_path,
    in_server       = SERVER_URL,
    in_service_name = SERVICE_NAME,
    in_cluster      = "",
    in_folder_type  = "EXISTING" if SERVER_FOLDER else "ROOT",
    in_folder       = SERVER_FOLDER if SERVER_FOLDER else "",
    in_startupType  = "STARTED",
    in_my_contents  = "NO_SHARE_ONLINE",
    in_public       = "PRIVATE",
    in_organization = "NO_SHARE_ORGANIZATION",
    in_groups       = None,
)

print(f"  Service published.")
print(f"  MapServer URL:     {map_server_url}")
print(f"  FeatureServer URL: {feature_server_url}")

# Portal item creation is asynchronous — the REST call returns before all
# items are fully registered.  Sleeping 8 seconds gives Portal time to create
# and index the Map Service and Feature Service content items so they show
# up in a content search.  Adjust if you see items missing in post_publish_ids.
print("  Waiting 8 seconds for Portal item registration to settle...")
time.sleep(8)

# Snapshot after publish.  Diff with pre_publish_ids to isolate new items.
post_publish_ids = {
    item.id
    for item in gis.content.search(query=f"owner:{username}", max_items=500)
}

# These are the items UploadServiceDefinition created — typically one Map Service
# item and one Feature Service item.  We explicitly exclude SD_ITEM_ID because
# that was uploaded in Step 6 (it's already in both snapshots).
service_item_ids = post_publish_ids - pre_publish_ids

# Print a manifest of what we're about to do so the operator can verify before
# anything is modified.
print(f"\n  Portal items to manage:")
print(f"    - {SD_ITEM_ID}  '{SERVICE_NAME}' (Service Definition) — will be deleted")
for item_id in service_item_ids:
    item  = gis.content.get(item_id)
    label = f"'{item.title}' ({item.type})" if item else "(unknown)"
    print(f"    - {item_id}  {label} — will be moved to {PORTAL_FOLDER} and protected")


# =============================================================================
# STEP 8 — Delete .sd item, move service items to PORTAL_FOLDER, protect them
# =============================================================================
# Three distinct actions here — explained in detail:
#
# ACTION A — Delete the .sd Portal item
#   The .sd is a staging artifact.  Once the service is live, the .sd serves
#   no purpose in Portal and just clutters the content library.  It is safe
#   to delete it; doing so does NOT affect the running service.
#   (The service runs from ArcGIS Server's own internal configuration, not
#    from the Portal .sd item.)
#
# ACTION B — Move service items to PORTAL_FOLDER
#   UploadServiceDefinition IGNORES the portalFolder setting from the .sddraft
#   and always drops new Map/Feature Service items in the root content library.
#   We move them manually here so they live alongside related content in the
#   organized folder structure.
#   If PORTAL_FOLDER doesn't exist yet, we create it first.
#
# ACTION C — Enable delete-protection on service items
#   Portal's "delete protection" flag prevents an item from being deleted
#   through the Portal UI or API unless protection is first disabled.
#   Why does this matter?  If someone accidentally deletes the Map Service or
#   Feature Service item from Portal, ArcGIS Server immediately stops that
#   service — taking it offline for all users.  Protection is a guardrail
#   against that.  To intentionally remove a service, you must:
#     1. Go to the item in Portal > Item Properties > Disable delete protection
#     2. Then delete the item (which also stops the server service)
#   Coordinate with the DBO before doing so.

print("\n" + "=" * 60)
print("STEP 8: Cleaning up .sd, moving and protecting service items...")
print("=" * 60)

# --- ACTION A: Delete the .sd upload item from Portal ---
sd_portal_item = gis.content.get(SD_ITEM_ID)   # Look up the item by the GUID we saved in Step 6
if sd_portal_item:
    sd_portal_item.delete()
    print(f"  ✓ Deleted .sd item {SD_ITEM_ID} from Portal.")
else:
    # If we can't find it (maybe it was manually deleted already), warn and
    # continue — this is non-critical.
    print(f"  WARNING: Could not retrieve .sd item {SD_ITEM_ID} — may already be gone.")

# --- Ensure the destination Portal folder exists before we try to move items into it ---
existing_folders = [f["title"] for f in gis.users.me.folders]
if PORTAL_FOLDER not in existing_folders:
    gis.content.create_folder(PORTAL_FOLDER)
    print(f"  Created Portal folder: {PORTAL_FOLDER}")

# --- ACTIONS B & C: Move each service item to the target folder, then protect it ---
for item_id in service_item_ids:
    item = gis.content.get(item_id)
    if not item:
        # If gis.content.get() returns None the item doesn't exist (or there's
        # a permissions issue).  Skip it and warn rather than crash the whole step.
        print(f"  WARNING: Could not retrieve item {item_id} — skipping.")
        continue

    # ACTION B: Move the item to PORTAL_FOLDER
    try:
        result = item.move(PORTAL_FOLDER)
        if result.get("success"):
            print(f"  ✓ Moved '{item.title}' ({item.type}) → {PORTAL_FOLDER}")
        else:
            # The API returned a response but didn't indicate success.  Print it
            # so the operator can investigate without the script aborting.
            print(f"  WARNING: Move returned unexpected response for {item_id}: {result}")
    except Exception as e:
        print(f"  ERROR moving {item_id}: {e}")

    # ACTION C: Enable delete-protection
    try:
        result = item.protect(enable=True)
        if result.get("success"):
            print(f"  ✓ Protected '{item.title}' ({item.type})")
        else:
            print(f"  WARNING: Protect returned unexpected response for {item_id}: {result}")
    except Exception as e:
        print(f"  ERROR protecting {item_id}: {e}")


# =============================================================================
# STEP 9 — Clean up local staging files
# =============================================================================
# The .sddraft and .sd files on local disk were only needed during the publish
# workflow.  They can be large (depending on the map), so we delete them now.
# The service does not depend on these local files — it runs from ArcGIS Server.

print("\n" + "=" * 60)
print("STEP 9: Cleaning up local staging files...")
print("=" * 60)

for f in [sddraft_path, sd_path]:
    if os.path.exists(f):
        os.remove(f)
        print(f"  Deleted: {f}")


# =============================================================================
# SUMMARY
# =============================================================================
# Print a final status board so the operator has a quick reference for the
# newly published service's URLs and the Portal item IDs that were created.
# This output is also useful to copy into a deployment log or ticket.

print("\n" + "=" * 60)
print("COMPLETE")
print("=" * 60)
print(f"  Service name:      {SERVICE_NAME}")
print(f"  Server folder:     {SERVER_FOLDER if SERVER_FOLDER else '(root)'}")
print(f"  MapServer URL:     {map_server_url}")
print(f"  FeatureServer URL: {feature_server_url}")
print(f"  Portal folder:     {PORTAL_FOLDER}")
print(f"  Portal items (delete-protected):")
for item_id in service_item_ids:
    item  = gis.content.get(item_id)
    label = f"'{item.title}' ({item.type})" if item else "(unknown)"
    print(f"    - {item_id}  {label}")
print()
print("  Items are protected — to delete from Portal you must first")
print("  unprotect them via item properties. Doing so WILL stop the")
print("  server service. Do not delete without coordinating with DBO.")
print("=" * 60)
