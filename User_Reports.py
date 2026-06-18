# =============================================================================
# USER INVENTORY SCRIPT
# !!!!!THIS STLL HAS ISSUES WOULD LIKE TO PRINT EACH USER'S INFORMATION TO A UNIQUE COLUMN AND STORAGE INFO IS BROKEN OR HARD TO UNDERSTAND!!!!
# =============================================================================
# PURPOSE:
#   Connect to an ArcGIS portal (AGOL or Enterprise) using your active ArcGIS
#   Pro sign-in, scan every user in that portal, and write a comprehensive CSV
#   file containing as much information as the API exposes per user account:
#   identity fields, role/license, login history, profile details, storage,
#   content counts, group memberships, and more.
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
#   Must be run as a portal administrator, or as a user with sufficient
#   privileges to view other users' profiles, to get full results.
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

import time
# ^^^ Used to convert portal epoch-millisecond timestamps to readable date strings.


# =============================================================================
# SECTION 1 — PORTAL CONNECTION
# =============================================================================

gis = GIS('pro')
# ^^^ Connects using the portal already active in ArcGIS Pro — no credentials
#     stored in this script.
#
#     ALTERNATIVES:
#       gis = GIS('home')                          → ArcGIS Notebook inside portal
#       gis = GIS("https://your-enterprise.com/portal")  → explicit Enterprise URL

print(f"\nConnected to portal : {gis.properties.portalHostname}")
print(f"Signed in as        : {gis.properties['user']['username']}\n")


# =============================================================================
# SECTION 2 — CONFIGURATION
# =============================================================================

OUTPUT_FILE_PATH = os.path.join(os.path.expanduser("~/Documents"), "user_inventory.csv")
# ^^^ Where to save the CSV on your local machine.
#     Defaults to your Windows Documents folder. To change it, replace this
#     line with a raw string path, e.g.:
#       OUTPUT_FILE_PATH = r"C:\GIS\Reports\user_inventory.csv"


# =============================================================================
# SECTION 3 — HELPER: EPOCH MILLISECONDS TO DATE STRING
# =============================================================================

def epoch_ms_to_date(epoch_ms):
    # -------------------------------------------------------------------------
    # Converts a portal Unix-epoch-millisecond timestamp to a DD/MM/YYYY string.
    # Returns "" if the value is 0, negative, or None (meaning "not set").
    # -------------------------------------------------------------------------

    if not epoch_ms or epoch_ms <= 0:
        return ""
    return time.strftime("%d/%m/%Y", time.localtime(epoch_ms / 1000))
    # ^^^ Divide by 1000 to convert ms → seconds, then format as local date.


# =============================================================================
# SECTION 4 — HELPER: SAFE PROPERTY READER
# =============================================================================

def safe_get(user, key, default=""):
    # -------------------------------------------------------------------------
    # WHAT THIS FUNCTION DOES:
    #   The ArcGIS API User object behaves like a hybrid — some properties are
    #   Python attributes (user.firstName) and some are dict-style keys backed
    #   by the raw JSON the portal returned (user['snippet']). When a key is
    #   simply absent from the portal's JSON response, accessing it either
    #   raises a KeyError (dict-style) or returns None (attribute-style).
    #
    #   This function tries both access patterns and returns 'default' (empty
    #   string) for anything that is missing, None, or raises any error at all.
    #   This means a missing or unsupported field always produces a blank CSV
    #   cell rather than crashing the script.
    #
    # PARAMETERS:
    #   user    : the User object from gis.users.search()
    #   key     : string name of the property to read
    #   default : value to return when the property is unavailable (default "")
    #
    # RETURNS:
    #   The property value as returned by the API, or default.
    # -------------------------------------------------------------------------

    try:
        # Try attribute-style access first (e.g. user.firstName).
        # getattr returns the 'default' sentinel if the attribute doesn't exist
        # at all, but User objects can also raise on attribute access for keys
        # absent from their underlying JSON — so we still need the outer try.
        value = getattr(user, key, None)

        if value is None:
            # Attribute either didn't exist or was explicitly None.
            # Fall through to dict-style access as a second attempt.
            value = user[key]

        # At this point value came from one of the two access patterns.
        # If it's still None, return default so the CSV cell is blank.
        if value is None:
            return default

        return value

    except Exception:
        # Any error (KeyError, AttributeError, TypeError, etc.) means the
        # property is simply not available for this user on this portal.
        # Return default silently — we never want one missing field to
        # prevent the rest of the user's data from being written.
        return default


# =============================================================================
# SECTION 5 — SEARCH FOR ALL USERS
# =============================================================================
#
# WHY NOT gis.users.search()?
#   On ArcGIS Enterprise, gis.users.search() crashes when the portal contains
#   "ghost" accounts — system/service accounts that have an internal GUID but
#   no resolvable username. The API auto-hydrates every user it finds, hitting
#   /community/users/<GUID> and getting a 404 back.
#
# THE FIX:
#   gis._portal.search_users() returns raw dicts without auto-hydrating.
#   We then only construct a proper User object for accounts that have a real
#   username, skipping any ghost accounts entirely.
#   Safe on AGOL too — same behavior, no side effects.
# =============================================================================

print("Searching for all users in the portal — this may take a moment...\n")

all_user_dicts = gis._portal.search_users(q="", max_users=10000)
# ^^^ Returns a list of raw user dicts without triggering hydration.
#     q="" matches all users. max_users=10000 removes the default cap of 100.

users = []
# ^^^ Will hold fully-constructed User objects ready for Section 6.

skipped = 0
# ^^^ Counts accounts skipped due to no username or hydration failure.

for u in all_user_dicts:
    uname = u.get("username")
    # ^^^ Pull the username string from the raw dict.
    #     Ghost/system accounts may have an 'id' (GUID) but no 'username' —
    #     those are exactly the ones that caused the original crash.

    if uname:
        try:
            users.append(gis.users.get(uname))
            # ^^^ gis.users.get() constructs a fully-hydrated User object by
            #     username. Safe because we know this username resolves correctly.
        except Exception as e:
            print(f"  [skip] Could not load '{uname}': {e}")
            skipped += 1
            # ^^^ If hydration still fails for any reason (permissions, stale
            #     account, etc.), log it and move on rather than crashing.
    else:
        skipped += 1
        # ^^^ No username = ghost account. Skip silently.

print(f"Found {len(users)} user(s) ({skipped} skipped). Collecting properties...\n")


# =============================================================================
# SECTION 6 — BUILD THE USER DATA COLLECTION
# =============================================================================
# Loops over every user and collects every available property into a list of
# dicts. One dict per user; one key per CSV column.
#
# COLUMNS COLLECTED:
#
#   IDENTITY
#     username        — unique portal login name
#     first_name      — given name (if set)
#     last_name       — family name (if set)
#     full_name       — display name as shown in the portal
#     email           — account email address
#     description     — user's bio / profile description (if set)
#
#   ACCESS & ROLE
#     level           — license level (1 = Viewer, 2 = Creator/Editor)
#     role            — built-in role name or custom role ID
#     role_id         — internal role identifier string
#     user_type       — license type (e.g. "creatorUT", "viewerUT")
#     disabled        — TRUE if the account has been deactivated
#     privileges      — semicolon-separated list of individual privilege strings
#
#   DATES & ACTIVITY
#     created         — date the account was created
#     last_login      — date the user last signed in (blank = never)
#     last_modified   — date the profile was last updated
#
#   STORAGE
#     storage_usage   — storage used by this user's content (bytes)
#     storage_quota   — per-user storage quota (bytes; 0 = org-level quota)
#
#   CONTENT
#     item_count      — number of items owned by this user, retrieved by
#                       searching content with owner filter. This is a separate
#                       API call per user, so it adds time on large portals.
#                       Set COUNT_ITEMS = False below to skip it for speed.
#
#   LOCATION & CULTURE
#     culture         — locale/language code (e.g. "en-US", "fr-FR")
#     region          — geographic region code (e.g. "US", "WO")
#     timezone        — timezone string (e.g. "America/New_York")
#
#   GROUPS
#     groups          — comma-separated list of group titles
#     group_count     — number of groups this user belongs to
#
# NOTE: Fields may be blank for non-admin scans or unpopulated accounts.
# =============================================================================

COUNT_ITEMS = True
# ^^^ Set to False to skip the per-user item count search.
#     Counting items requires one extra API call per user, which adds noticeable
#     time on portals with many users. When True, 'item_count' is populated.
#     When False, 'item_count' will be blank for every user.

user_rows = []
# ^^^ Accumulates one dict per successfully processed user.

for i, user in enumerate(users, start=1):
    # ^^^ enumerate gives us a counter 'i' so we can print progress.

    try:
        username = user.username # triggers hydration — catches 404 here safely
        print(f"  Processing {i}/{len(users)}: {user.username}")

        # -- Groups -----------------------------------------------------------

        user_groups = []
        for grp in user.groups:
            # ^^^ user.groups is a list of Group objects.
            try:
                user_groups.append(grp.title)
            except Exception:
                user_groups.append("External private group")
                # ^^^ External secured groups raise when their title is accessed
                #     by users without visibility into that group.

        groups_str = ", ".join(user_groups)

        # -- Privileges -------------------------------------------------------

        try:
            raw_privs = safe_get(user, 'privileges', [])
            privileges_str = "; ".join(raw_privs) if raw_privs else ""
            # ^^^ Join individual privilege strings with semicolons.
            #     Semicolons chosen over commas to avoid confusion in a CSV.
        except Exception:
            privileges_str = ""

        # -- Item count -------------------------------------------------------
        # itemCount is NOT a direct attribute on the User object — it is not
        # included in the users.search() response payload. The only reliable
        # way to get it is to search content filtered to that owner.

        if COUNT_ITEMS:
            try:
                owned_items = gis.content.search(
                    query=f"owner:{user.username}",
                    max_items=10000
                )
                item_count = len(owned_items)
                # ^^^ gis.content.search returns a list; len() gives the count.
                #     max_items=10000 ensures we don't undercount prolific users.
            except Exception:
                item_count = ""
                # ^^^ If the search fails (permissions, etc.), leave blank.
        else:
            item_count = ""

        # -- Build the row dict -----------------------------------------------

        user_rows.append({

            # IDENTITY
            'username':      safe_get(user, 'username'),
            'first_name':    safe_get(user, 'firstName'),
            'last_name':     safe_get(user, 'lastName'),
            'full_name':     safe_get(user, 'fullName'),
            'email':         safe_get(user, 'email'),
            'description':   safe_get(user, 'description'),

            # ACCESS & ROLE
            'level':         safe_get(user, 'level'),
            'role':          safe_get(user, 'role'),
            'role_id':       safe_get(user, 'roleId'),
            'user_type':     safe_get(user, 'userType'),
            'disabled':      safe_get(user, 'disabled'),
            'privileges':    privileges_str,

            # DATES & ACTIVITY
            'created':       epoch_ms_to_date(safe_get(user, 'created', 0)),
            'last_login':    epoch_ms_to_date(safe_get(user, 'lastLogin', 0)),
            'last_modified': epoch_ms_to_date(safe_get(user, 'modified', 0)),

            # STORAGE
            'storage_usage': safe_get(user, 'storageUsage'),
            'storage_quota': safe_get(user, 'storageQuota'),

            # CONTENT
            'item_count':    item_count,

            # LOCATION & CULTURE
            'culture':       safe_get(user, 'culture'),
            'region':        safe_get(user, 'region'),
            'timezone':      safe_get(user, 'timezone'),

            # GROUPS
            'groups':        groups_str,
            'group_count':   len(user_groups),
        })

    except Exception as e:
        print(f"  [skip] User {i} could not be hydrated or processed: {e}")
        continue
        # ^^^ If anything fails at the outer level for this user, log it and
        #     move on. The user is skipped from the CSV rather than crashing
        #     the entire run.

print(f"\nCollected data for {len(user_rows)} user(s). Writing CSV...\n")


# =============================================================================
# SECTION 7 — WRITE RESULTS TO CSV ON YOUR LOCAL MACHINE
# =============================================================================

FIELD_NAMES = [
    'username', 'first_name', 'last_name', 'full_name', 'email', 'description',
    'level', 'role', 'role_id', 'user_type', 'disabled', 'privileges',
    'created', 'last_login', 'last_modified',
    'storage_usage', 'storage_quota', 'item_count',
    'culture', 'region', 'timezone',
    'groups', 'group_count',
]
# ^^^ Column names for the CSV header row. Must match keys used in user_rows dicts.

with open(OUTPUT_FILE_PATH, mode='w', newline='', encoding='utf-8') as f:
# ^^^ 'w' creates or overwrites the file. newline='' prevents Windows double-spacing.
# ^^^ encoding='utf-8' handles special characters in names/descriptions correctly.

    writer = csv.DictWriter(f, fieldnames=FIELD_NAMES, extrasaction='ignore')
    # ^^^ extrasaction='ignore' silently drops any unexpected keys rather than
    #     raising a ValueError — a safety net against API response changes.

    writer.writeheader()
    writer.writerows(user_rows)


# =============================================================================
# SECTION 8 — CONFIRMATION AND OPEN FILE
# =============================================================================

print(f"CSV written to : {OUTPUT_FILE_PATH}")
print(f"Users exported : {len(user_rows)}")
print("\nDone. No portal users or items were modified.")

#os.startfile(OUTPUT_FILE_PATH)
# ^^^ Opens the CSV in Excel (or your default .csv application) automatically.
#     Comment this line out if running on macOS/Linux — os.startfile() is
#     Windows-only. On macOS use: subprocess.call(['open', OUTPUT_FILE_PATH])