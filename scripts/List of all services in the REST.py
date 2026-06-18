"""
====================================================================
 ARCGIS REST SERVICES CRAWLER
====================================================================
This script is designed for ArcGIS REST Services (the format you're
using -- e.g. https://.../arcgis/rest/services/...).

ArcGIS REST services have a predictable structure:

    https://<server>/arcgis/rest/services/<ServiceName>/<ServiceType>
        |
        +-- Layers (e.g. Layer 0, Layer 1, ...) -- each layer has
        |       its own set of "fields" (column definitions)
        |
        +-- Each layer has FEATURES (the actual records/items),
                and each feature has ATTRIBUTES (the metadata you
                want -- e.g. name, address, type, status, etc.)

This script will:
  1. Connect to a FeatureServer (or MapServer) and list all layers.
  2. For each layer, query ALL features (handling pagination
     automatically using ArcGIS's resultOffset/resultRecordCount).
  3. Save each feature's attributes (metadata) + geometry (optional)
     to a JSON file, one file per layer.

You can append "?f=json" to ANY ArcGIS REST URL to get JSON instead
of the HTML directory page -- that's the trick this whole script
relies on.
====================================================================
"""

import requests
import json
import time
import os
import csv
import getpass
import urllib3
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)


# ====================================================================
# CONFIGURATION -- edit these values for your service
# ====================================================================

# The URL of the SERVICE or the SERVICES FOLDER/CATALOG.
# Examples:
#   Single service: https://.../arcgis/rest/services/PublicDenisonData/FeatureServer
#   Folder crawl:   https://.../arcgis/rest/services/PublicDenisonData
#
# NOTE: FeatureServer is generally preferred over MapServer for
# pulling attribute data, since it's designed for queries.
def prompt_for_service_url():
    """Prompt for the service or folder URL and exit cleanly on blank or canceled input."""
    try:
        service_url = input(
            "Enter the ArcGIS REST service or folder URL (for example: https://.../FeatureServer or https://.../arcgis/rest/services): "
        ).strip()
    except KeyboardInterrupt:
        print("\nCancelled. Aborting gracefully.")
        raise SystemExit(0)
    except EOFError:
        print("\nNo service URL provided. Aborting gracefully.")
        raise SystemExit(0)

    if not service_url:
        print("No service URL provided. Aborting gracefully.")
        raise SystemExit(0)

    return service_url


SERVICE_URL = prompt_for_service_url()

# No authentication needed for your service, but if you ever need
# auth (e.g. a token), you'd add it here, e.g.:
#   PARAMS_EXTRA = {"token": "YOUR_TOKEN"}
# You can also set ARCGIS_TOKEN / ARCGIS_USERNAME / ARCGIS_PASSWORD
# as environment variables before running the script.
PARAMS_EXTRA = {}
PORTAL_URL = os.environ.get("ARCGIS_PORTAL_URL", "").strip()
USERNAME = os.environ.get("ARCGIS_USERNAME", "").strip()
PASSWORD = os.environ.get("ARCGIS_PASSWORD", "").strip()
AUTH_TOKEN = os.environ.get("ARCGIS_TOKEN", "").strip()

# How many features to request per page. ArcGIS servers often cap
# this (commonly 1000 or 2000) -- if you ask for more than the
# server allows, it will silently cap it, which is fine.
PAGE_SIZE = 1000

# Whether to include geometry (shape/location data) in the output.
# Set to False if you ONLY care about attribute metadata (smaller
# output files, faster).
INCLUDE_GEOMETRY = False

# Whether to fetch record-level data for each layer.
# Set to False if you only want layer metadata and field definitions.
INCLUDE_RECORDS = False

# Where to save the output files.
#
# os.path.expanduser("~") resolves to your user profile folder
# automatically:
#   - Windows: C:\Users\<YourName>
#   - Mac/Linux: /Users/<YourName> or /home/<yourname>
#
# So this points to: <YourUserFolder>/Documents/arcgis_export
# You can also hardcode a full path instead if you prefer, e.g.:
#   OUTPUT_DIR = r"C:\Users\YourName\Documents\arcgis_export"
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "arcgis_export")
def get_service_name(service_url):
    """Derive a filesystem-safe service name from the REST URL."""
    parts = service_url.rstrip("/").split("/")
    if len(parts) >= 2:
        service_name = parts[-2] if parts[-1].lower() in {"featureserver", "mapserver"} else parts[-1]
    else:
        service_name = "service"

    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in service_name)


def build_service_url(root_url, service):
    """Build a valid ArcGIS service URL from a catalog service entry."""
    service_url = (service.get("url") or "").strip()
    if service_url:
        return service_url

    service_name = (service.get("name") or "").strip()
    service_type = (service.get("type") or "").strip()
    if not service_name or not service_type:
        return ""

    root_parts = root_url.rstrip("/").split("/")
    services_idx = root_parts.index("services") if "services" in root_parts else -1
    current_path_parts = root_parts[services_idx + 1:] if services_idx >= 0 else []
    service_name_parts = service_name.split("/")

    for folder_segment in current_path_parts:
        if service_name_parts and service_name_parts[0].lower() == folder_segment.lower():
            service_name_parts.pop(0)
        else:
            break

    service_path = "/".join(part for part in service_name_parts if part)
    if service_path:
        return f"{root_url.rstrip('/')}/{service_path}/{service_type}"
    return f"{root_url.rstrip('/')}/{service_type}"


def discover_service_urls(root_url):
    """Discover all service URLs beneath a services catalog or folder path."""
    root_url = root_url.rstrip("/")
    print(f"Inspecting catalog: {root_url}")

    try:
        data = get_json_response(
            root_url,
            params={"f": "json", **PARAMS_EXTRA},
            timeout=30,
        )
    except Exception as exc:
        print(f"  WARNING: Could not inspect {root_url}: {exc}")
        return []

    if "error" in data:
        raise RuntimeError(f"ArcGIS returned an error: {data['error']}")

    if isinstance(data.get("layers"), list) and "services" not in data and "folders" not in data:
        return [root_url]

    service_urls = []
    for service in data.get("services", []):
        service_url = build_service_url(root_url, service)
        if service_url:
            service_urls.append(service_url)

    for folder_name in data.get("folders", []):
        folder_url = f"{root_url}/{folder_name}"
        service_urls.extend(discover_service_urls(folder_url))

    return service_urls


SUMMARY_CSV = os.path.join(OUTPUT_DIR, f"{get_service_name(SERVICE_URL)}_layer_summary.csv")

# Pause between requests (seconds) to be polite to the server.
REQUEST_DELAY = 0.2


def get_access_token(force_refresh=False):
    """Resolve an ArcGIS token from a direct token entry, ArcGIS Pro, or credentials."""
    global AUTH_TOKEN, USERNAME, PASSWORD, PARAMS_EXTRA

    if not force_refresh and PARAMS_EXTRA.get("token"):
        return PARAMS_EXTRA["token"]

    if not force_refresh and AUTH_TOKEN:
        PARAMS_EXTRA["token"] = AUTH_TOKEN
        return AUTH_TOKEN

    if not force_refresh:
        try:
            import arcpy

            signin_token = arcpy.GetSigninToken()
            if isinstance(signin_token, dict) and signin_token.get("token"):
                AUTH_TOKEN = signin_token["token"]
                PARAMS_EXTRA["token"] = AUTH_TOKEN
                print("Using ArcGIS Pro sign-in token.")
                return AUTH_TOKEN
        except Exception as exc:
            print(f"ArcGIS Pro sign-in token unavailable: {exc}")

    if not USERNAME:
        token_or_user = input(
            "Enter an ArcGIS token (or press Enter to use username/password): "
        ).strip()
        if token_or_user:
            AUTH_TOKEN = token_or_user
            PARAMS_EXTRA["token"] = AUTH_TOKEN
            return AUTH_TOKEN

        USERNAME = input("ArcGIS username (leave blank to skip): ").strip()

    if USERNAME and not PASSWORD:
        PASSWORD = getpass.getpass("ArcGIS password: ")

    if not USERNAME or not PASSWORD:
        return None

    portal = PORTAL_URL or SERVICE_URL.split("/arcgis/rest")[0]
    endpoints = [
        f"{portal.rstrip('/')}/sharing/rest/generateToken",
        f"{portal.rstrip('/')}/arcgis/tokens/generateToken",
        f"{portal.rstrip('/')}/arcgis/admin/generateToken",
    ]

    for endpoint in endpoints:
        try:
            payload = {
                "username": USERNAME,
                "password": PASSWORD,
                "expiration": 60,
                "f": "json",
            }
            response = requests.post(endpoint, data=payload, timeout=30, verify=False)
            response.raise_for_status()
            data = response.json()
            if data.get("token"):
                AUTH_TOKEN = data["token"]
                PARAMS_EXTRA["token"] = AUTH_TOKEN
                print(f"Acquired ArcGIS token from {endpoint}")
                return AUTH_TOKEN
        except Exception as exc:
            print(f"Token request to {endpoint} failed: {exc}")

    return None


def get_json_response(url, params=None, timeout=30):
    """Fetch JSON from an ArcGIS REST endpoint, using a token or credentials when needed."""
    params = dict(params or {})

    for attempt in range(2):
        if not params.get("token"):
            token = get_access_token(force_refresh=(attempt > 0))
            if token:
                params["token"] = token
                PARAMS_EXTRA["token"] = token

        try:
            response = requests.get(url, params=params, timeout=timeout, verify=False)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.SSLError:
            print(f"SSL verification failed for {url}; retrying without certificate verification.")
            response = requests.get(url, params=params, timeout=timeout, verify=False)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Request to {url} failed: {exc}") from exc

        if isinstance(data, dict) and data.get("error", {}).get("code") in {498, 499} and attempt == 0:
            print("ArcGIS reported token-required access. Retrying once after refreshing authentication.")
            continue

        break

    if isinstance(data, dict) and data.get("error", {}).get("code") in {400, 498, 499}:
        raise RuntimeError(f"ArcGIS returned an error: {data['error']}")

    return data


# ====================================================================
# STEP 1: Get the list of layers in this service
# ====================================================================

def get_service_layers(service_url):
    """
    Fetch the service's metadata (?f=json) and return its list of
    layers. Each layer is a dict like:
        {"id": 0, "name": "Parcels", ...}
    """
    print(f"Fetching service metadata from: {service_url}?f=json")

    data = get_json_response(
        service_url,
        params={"f": "json", **PARAMS_EXTRA},
        timeout=30,
    )

    # Sanity check: make sure ArcGIS didn't return an error object
    if "error" in data:
        raise RuntimeError(f"ArcGIS returned an error: {data['error']}")

    layers = data.get("layers", [])
    # Some services also have "tables" (non-spatial data tables) --
    # these often contain useful metadata too (e.g. lookup tables).
    tables = data.get("tables", [])

    print(f"  -> Found {len(layers)} layer(s) and {len(tables)} table(s).")

    # Combine layers and tables into one list, since both can be
    # queried the same way.
    return layers + tables


# ====================================================================
# STEP 2: Get field definitions for a layer (optional but useful --
#         tells you what metadata fields exist before querying)
# ====================================================================

def get_layer_fields(layer_url):
    """
    Fetch a single layer's metadata and return its list of field
    definitions. Each field is a dict like:
        {"name": "PARCEL_ID", "type": "esriFieldTypeString", "alias": "Parcel ID"}
    """
    data = get_json_response(
        layer_url,
        params={"f": "json", **PARAMS_EXTRA},
        timeout=30,
    )

    if "error" in data:
        raise RuntimeError(f"ArcGIS returned an error: {data['error']}")

    return data.get("fields", [])


# ====================================================================
# STEP 3: Query ALL features from a layer, handling pagination
# ====================================================================

def get_all_features(layer_url, page_size=PAGE_SIZE, include_geometry=False):
    """
    Query a layer's /query endpoint repeatedly, paging through
    results using resultOffset + resultRecordCount, until no more
    features are returned.

    Returns a list of "feature" dicts, each containing an
    "attributes" key (the metadata) and optionally a "geometry" key.
    """
    query_url = layer_url.rstrip("/") + "/query"

    all_features = []
    offset = 0
    max_pages = 1000

    try:
        count_url = layer_url.rstrip("/") + "/query"
        count_params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "returnCountOnly": "true",
            **PARAMS_EXTRA,
        }
        token = get_access_token()
        if token:
            count_params["token"] = token
        count_response = requests.get(count_url, params=count_params, timeout=60, verify=False)
        count_response.raise_for_status()
        feature_count = count_response.json().get("count", 0)
        print(f"    Layer has approximately {feature_count} feature(s).")
    except Exception as exc:
        feature_count = None
        print(f"    Could not retrieve feature count: {exc}")

    while True:
        # ------------------------------------------------------
        # Build the query parameters.
        #
        #   where=1=1        -> match ALL records (no filtering)
        #   outFields=*       -> return ALL attribute fields
        #   f=json            -> return JSON (not HTML)
        #   resultOffset      -> "skip" this many records (pagination)
        #   resultRecordCount -> "page size"
        #   returnGeometry    -> whether to include shape/location data
        # ------------------------------------------------------
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "returnGeometry": "true" if include_geometry else "false",
            **PARAMS_EXTRA,
        }

        print(f"    Querying offset={offset}, pageSize={page_size}...")

        try:
            data = get_json_response(query_url, params=params, timeout=60)
        except requests.exceptions.RequestException as e:
            print(f"    ERROR: {e}")
            break

        # ArcGIS returns errors as JSON with an "error" key, even
        # though the HTTP status code might still be 200.
        if "error" in data:
            print(f"    ERROR from ArcGIS: {data['error']}")
            break

        features = data.get("features", [])

        if not features:
            print("    No more features. Done with this layer.")
            break

        all_features.extend(features)
        print(f"    -> Got {len(features)} feature(s) "
              f"(total so far: {len(all_features)})")

        # ------------------------------------------------------
        # Decide whether to fetch another page.
        #
        # ArcGIS services can return exceededTransferLimit=True for a long
        # time even when the layer is small or the service is enforcing a
        # maximum page size. To avoid infinite paging, stop when one of the
        # following is true:
        #   1) we got fewer features than requested and the server did not
        #      report more data,
        #   2) we have requested too many pages for this layer, or
        #   3) the same offset is being requested again (repeat-page loop).
        # ------------------------------------------------------
        exceeded_limit = data.get("exceededTransferLimit", False)
        if not exceeded_limit and len(features) < page_size:
            print("    Reached last page (fewer features than page size, "
                  "and exceededTransferLimit not set).")
            break

        if len(features) == 0:
            print("    No features returned on this page. Stopping.")
            break

        if feature_count is not None and len(all_features) >= feature_count:
            print("    Retrieved the full feature count for this layer. Stopping.")
            break

        if offset >= (page_size * max_pages):
            print("    Reached the maximum page limit; stopping.")
            break

        # Move to the next page
        offset += len(features)

        if REQUEST_DELAY > 0:
            time.sleep(REQUEST_DELAY)

    return all_features


# ====================================================================
# STEP 4: Flatten a feature into a simple dict (attributes + geometry)
# ====================================================================

def flatten_feature(feature, include_geometry=False):
    """
    ArcGIS features look like:
        {
            "attributes": {"OBJECTID": 1, "NAME": "City Hall", ...},
            "geometry": {"x": -96.xxx, "y": 33.xxx}   <- optional
        }

    This function flattens that into a single dict, optionally
    including geometry under a "geometry" key.
    """
    result = dict(feature.get("attributes", {}))

    if include_geometry and "geometry" in feature:
        result["_geometry"] = feature["geometry"]

    return result


# ====================================================================
# STEP 5: Write a list of flattened feature dicts to a CSV file
# ====================================================================

def write_features_to_csv(features, output_path):
    """
    Write a list of dicts (each dict = one feature's attributes,
    possibly plus "_geometry") to a CSV file.

    CSV files require a fixed set of columns, but different
    features *could* theoretically have different keys (this is
    rare for ArcGIS layers, since all features in a layer normally
    share the same schema, but we handle it safely just in case).

    We do this by:
      1. Scanning ALL features first to build the full set of
         column names (preserving the order they're first seen in).
      2. Writing the header row, then each feature as a row,
         filling in blanks for any missing fields.
    """
    if not features:
        print("    No features to write -- skipping CSV.")
        return

    # ------------------------------------------------------
    # Step 1: Collect all unique column names across all features,
    # preserving first-seen order.
    # ------------------------------------------------------
    fieldnames = []
    seen = set()
    for feature in features:
        for key in feature.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    # ------------------------------------------------------
    # Step 2: Write the CSV.
    #
    # newline="" is required on Windows to prevent extra blank
    # lines between rows.
    #
    # extrasaction="ignore" + restval="" handle any
    # missing/extra keys gracefully.
    # ------------------------------------------------------
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
            restval="",
        )
        writer.writeheader()

        for feature in features:
            # Convert any nested dicts/lists (e.g. "_geometry") to
            # JSON strings so they fit cleanly into a single CSV cell.
            row = {}
            for key, value in feature.items():
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value)
                else:
                    row[key] = value
            writer.writerow(row)

    print(f"    Wrote {len(features)} row(s) with "
          f"{len(fieldnames)} column(s) to CSV.")




def main():
    # Make sure our output folder exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ----------------------------------------------------------
    # Step 1: Discover all services in the input path
    # ----------------------------------------------------------
    discovered_services = discover_service_urls(SERVICE_URL)

    if not discovered_services:
        print("No services found. Double-check SERVICE_URL.")
        return

    rows = []
    root_name = get_service_name(SERVICE_URL)
    summary_csv_path = os.path.join(OUTPUT_DIR, f"{root_name}_layer_summary.csv")
    global SUMMARY_CSV
    SUMMARY_CSV = summary_csv_path

    processed_services = 0
    skipped_services = 0
    successful_services = 0

    print(f"Discovered {len(discovered_services)} service(s) to process.")

    # ----------------------------------------------------------
    # Step 2: For each discovered service, gather metadata and write rows
    # ----------------------------------------------------------
    for service_url in discovered_services:
        print("\n" + "=" * 60)
        print(f"Processing service: {service_url}")
        print("=" * 60)

        processed_services += 1

        try:
            layers = get_service_layers(service_url)
        except Exception as exc:
            skipped_services += 1
            print(f"  WARNING: Could not process {service_url}: {exc}")
            continue

        if not layers:
            skipped_services += 1
            print("  No layers found for this service.")
            continue

        successful_services += 1
        service_name = get_service_name(service_url)

        for layer in layers:
            layer_id = layer.get("id")
            layer_name = layer.get("name", f"layer_{layer_id}")

            # Build the full URL for this specific layer, e.g.:
            #   https://.../FeatureServer/0
            layer_url = f"{service_url.rstrip('/')}/{layer_id}"

            print("\n" + "-" * 60)
            print(f"Layer {layer_id}: {layer_name}")
            print(f"URL: {layer_url}")
            print("-" * 60)

            # Get field definitions (useful for understanding what
            # metadata is available -- printed for your reference)
            try:
                fields = get_layer_fields(layer_url)
                field_names = [f.get("name") for f in fields]
                print(f"Fields ({len(field_names)}): {field_names}")
            except Exception as e:
                print(f"  WARNING: Could not fetch fields: {e}")
                fields = []

            if INCLUDE_RECORDS:
                features = get_all_features(
                    layer_url,
                    page_size=PAGE_SIZE,
                    include_geometry=INCLUDE_GEOMETRY,
                )
                feature_count = len(features)
                print(f"\nTotal features retrieved for '{layer_name}': {feature_count}")
            else:
                feature_count = None
                print(f"\nSkipping record fetch for '{layer_name}'")

            rows.append(
                {
                    "service_name": service_name,
                    "service_url": service_url,
                    "layer_id": layer_id,
                    "layer_name": layer_name,
                    "field_count": len(fields),
                    "field_names": "; ".join(f.get("name", "") for f in fields),
                    "feature_count": feature_count if feature_count is not None else "",
                }
            )

    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "service_name",
                "service_url",
                "layer_id",
                "layer_name",
                "field_count",
                "field_names",
                "feature_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote layer summary CSV to: {SUMMARY_CSV}")
    print("\n" + "=" * 60)
    print("Crawl summary")
    print(f"  Services discovered: {len(discovered_services)}")
    print(f"  Services attempted: {processed_services}")
    print(f"  Services succeeded: {successful_services}")
    print(f"  Services skipped: {skipped_services}")
    print("=" * 60)


if __name__ == "__main__":
    main()
