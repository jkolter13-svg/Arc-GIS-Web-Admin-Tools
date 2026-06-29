# Arc-GIS-Web-Admin-Tools

A collection of read-only Python scripts for inventorying and auditing ArcGIS Online (AGOL) and ArcGIS Enterprise portals. Every script in this toolkit uses only GET requests — nothing in your portal is ever created, modified, or deleted. The only output from each script is one or more CSV files written to your local machine.

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [How to Run](#how-to-run)
- [Scripts](#scripts)
  - [Service_Report.py](#service_reportpy)
  - [Search_Webmaps_for_Services.py](#search_webmaps_for_servicespy)
  - [Find_Unused_Services.py](#find_unused_servicespy)
  - [List_of_all_services_in_the_REST.py](#list_of_all_services_in_the_restpy)
  - [Metadata_Report.py](#metadata_reportpy)
  - [User_Reports.py](#user_reportspy)
  - [CSV_Mergeing_tool.py](#csv_mergeing_toolpy)
  - [Publish_to_Federated_Server.py](#publish_to_federated_serverpy)
- [Output Files Reference](#output-files-reference)
- [Authentication Options](#authentication-options)
- [Known Issues / Work in Progress](#known-issues--work-in-progress)
- [Credits and License](#credits-and-license)

---

## Overview

Managing a large ArcGIS portal means knowing what you have. These scripts answer questions like:

- What services are published in my portal, and what layers do they contain?
- Which web maps are referencing which services?
- Are there any services that no web map actually uses?
- Who are my portal users, and what are their roles and group memberships?
- What items (maps, apps, surveys, etc.) exist in the portal, and do they have descriptions?
- I have a dozen CSV exports — can I merge them into one file quickly?

Each script is self-contained and heavily commented for readability. They are designed to be pasted directly into the ArcGIS Pro Python window or run inside an ArcGIS Notebook.

---

## Requirements

- **ArcGIS Pro 3.x** with the bundled Python environment (ArcGIS API for Python 2.4.x)
- An active sign-in to the target portal inside ArcGIS Pro before running any script
- **CSV_Mergeing_tool.py only:** `pandas` must be installed in your Python environment (`pip install pandas`)

---

## How to Run

1. Open ArcGIS Pro and sign in to the portal you want to audit.
2. Open the **Python window** (Analysis tab → Python) or create an **ArcGIS Notebook**.
3. Paste the script into the window, or open the `.py` file directly.
4. Review the **CONFIGURATION** section near the top of each script and adjust any settings (output path, filters, toggles) before running.
5. Run the script. Output CSVs are saved to your local `~/Documents` folder by default.

> **Note:** Scripts that scan large portals (thousands of items, users, or services) may take several minutes to complete. Progress is printed to the console as each item is processed.

---

## Scripts

### Service_Report.py

**What it does:** Scans every Map Image Service, Feature Service, Vector Tile Service, and Image Service in the portal and writes a comprehensive inventory CSV.

**Output:** `~/Documents/service_inventory.csv`

**Columns:**

| Column | Description |
|---|---|
| `service_name` | Item title |
| `service_type` | Service type (Feature Service, Map Service, etc.) |
| `service_id` | Portal item GUID |
| `service_url` | REST endpoint URL |
| `owner` | Portal username of the owner |
| `created` | Creation date |
| `last_modified` | Date last modified |
| `service_layers` | Comma-separated list of layer names |
| `layer_count` | Number of layers |
| `sharing` | Sharing level (private, org, public) |
| `shared_groups` | Groups the service is shared with |
| `summary` | Item snippet/summary |
| `tags` | Item tags |
| `num_views` | Total view count |

**Configuration options:**
- `OUTPUT_FILE_PATH` — where to save the CSV
- `GET_LAYERS` — set to `False` to skip live layer reads (faster on large portals or when services are behind a firewall)

---

### Search_Webmaps_for_Services.py

**What it does:** Functionally identical to `Pull_every_web_service.py` — finds every Web Map, extracts all layer service URLs, and exports the same two CSV files. This script was updated and commented separately and may reflect a slightly different revision.

**Output:** Same as `Pull_every_web_service.py`

> If you only need one of these two scripts, either will work. Run both if you want to cross-check results.

---

### Find_Unused_Services.py

**What it does:** Combines the logic of the service inventory and web map scan to answer a specific question: **which services are published in the portal but not referenced by any web map?** Results are printed to the console and saved to a CSV.

**Output:** `~/Documents/unused_services.csv`

**Columns:**

| Column | Description |
|---|---|
| `title` | Service item title |
| `type` | Service type |
| `service_url` | REST endpoint URL |
| `portal_link` | Direct URL to the item's portal page |

**How it works:** Service URLs from the portal inventory are cross-referenced against all layer URLs found in all web maps using a substring match (so a service at `.../MapServer` will correctly match a layer reference to `.../MapServer/0`). Services with no substring match in any web map layer URL are flagged as unused.

> **Important caveat:** "Not in any web map" does not necessarily mean truly unused — a service may still be consumed by a Dashboard, Experience Builder app, Field Maps form, or other application type. Treat the output as a starting point for investigation, not a final decommission list.

---

### List_of_all_services_in_the_REST.py

**What it does:** Crawls an ArcGIS REST services endpoint (a FeatureServer, MapServer, or an entire services catalog/folder) and writes a layer summary CSV. Unlike the portal-based scripts above, this script queries the REST API directly using HTTP — it does not require ArcGIS Pro or a portal connection.

**Output:** `~/Documents/arcgis_export/<service_name>_layer_summary.csv`

**Columns:**

| Column | Description |
|---|---|
| `service_name` | Derived name from the REST URL |
| `service_url` | REST endpoint URL |
| `layer_id` | Layer index ID |
| `layer_name` | Layer name |
| `field_count` | Number of fields in the layer |
| `field_names` | Semicolon-separated list of field names |
| `feature_count` | Total feature count (if `INCLUDE_RECORDS = True`) |

**Configuration options:**
- `SERVICE_URL` — prompted interactively at runtime; accepts a single service URL or a services folder/catalog URL for bulk crawling
- `PAGE_SIZE` — features per page request (default 1000)
- `INCLUDE_GEOMETRY` — set to `True` to include geometry in feature exports
- `INCLUDE_RECORDS` — set to `True` to fetch actual feature-level data (not just layer metadata)
- `OUTPUT_DIR` — where to save output files
- `REQUEST_DELAY` — pause between requests in seconds (default 0.2) to be polite to the server

**Authentication:** Supports token via environment variable (`ARCGIS_TOKEN`), ArcGIS Pro sign-in (`arcpy.GetSigninToken()`), or interactive username/password prompt.

---

### Metadata_Report.py

**What it does:** Scans every item in the portal (or items owned by a specific user) and writes a CSV with each item's title, type, ID, summary, and description. Useful for finding items with missing or incomplete metadata.

**Output:** `~/Documents/item_inventory.csv`

**Columns:**

| Column | Description |
|---|---|
| `title` | Item title |
| `type` | Esri item type (Feature Service, Web Map, Dashboard, etc.) |
| `id` | Portal item GUID |
| `summary` | Item snippet/short summary |
| `description` | Full item description (may contain HTML) |

**Configuration options:**
- `OUTPUT_FILE_PATH` — where to save the CSV
- `ITEM_OWNER` — set to a portal username to scan only that user's items; leave empty (`""`) to scan the entire portal
- `EXCLUDED_TYPES` — a set of item type strings to skip (defaults exclude `Code Attachment`, `Mobile Map Package`, `Layer Template`, `Mobile Application`)

---

### User_Reports.py

**What it does:** Scans every user account in the portal and writes a comprehensive CSV with identity, role/license, login history, storage, content count, group memberships, and privileges.

**Output:** `~/Documents/user_inventory.csv`

**Columns:**

| Column | Description |
|---|---|
| `username` | Portal username |
| `first_name`, `last_name`, `full_name` | Name fields |
| `email` | Email address |
| `level` | Account level (1, 2, etc.) |
| `role` | Role name |
| `role_id` | Role ID string |
| `user_type` | User type (creatorUT, editorUT, etc.) |
| `disabled` | Whether the account is disabled |
| `privileges` | Semicolon-separated list of privileges |
| `created` | Account creation date (DD/MM/YYYY) |
| `last_login` | Last sign-in date (blank = never) |
| `last_modified` | Profile last updated date |
| `storage_usage` | Storage used in bytes |
| `storage_quota` | Per-user quota in bytes (0 = org-level quota) |
| `item_count` | Number of items owned by this user |
| `culture` | Locale/language code |
| `region` | Geographic region code |
| `timezone` | Timezone string |
| `groups` | Comma-separated list of group titles |
| `group_count` | Number of groups |

**Configuration options:**
- `OUTPUT_FILE_PATH` — where to save the CSV
- `COUNT_ITEMS` — set to `False` to skip the per-user item count search (one API call per user; can be slow on large portals)

**Requirements:** Must be run as a portal administrator, or as a user with privileges to view other users' profiles, for full results.

> ⚠️ **Known issue:** This script still has open issues. Storage information may be difficult to interpret, and per-user data ideally would output to unique columns. See [Known Issues](#known-issues--work-in-progress) below.

---

### CSV_Mergeing_tool.py

**What it does:** A standalone GUI utility (no ArcGIS connection required) that merges all CSV and Excel files from a selected folder into a single output file. Adds a `Source_File` column to every row so you can trace each record back to its origin file after merging.

**Supported input formats:** `.csv`, `.xlsx`, `.xls`

**Output format:** `.csv` or `.xlsx` (determined by the extension you provide for the output file path; defaults to `.xlsx` if no extension is given)

**How to run:** Execute the script directly from any Python environment that has `tkinter` and `pandas` installed. Two dialog boxes will appear asking for the input folder and the output file path. No ArcGIS Pro or portal connection is needed.

```bash
python CSV_Mergeing_tool.py
```

**Typical workflow:** Run several of the portal audit scripts above, then use this tool to combine all the resulting CSVs from a folder into one master spreadsheet for analysis or reporting.

---

## Output Files Reference

| Script | Output File | Default Location |
|---|---|---|
| Service_Report.py | `service_inventory.csv` | `~/Documents/` |
| Pull_every_web_service.py | `all_layers.csv`, `unique_services.csv` | `~/Documents/` |
| Search_Webmaps_for_Services.py | `all_layers.csv`, `unique_services.csv` | `~/Documents/` |
| Find_Unused_Services.py | `unused_services.csv` | `~/Documents/` |
| List_of_all_services_in_the_REST.py | `<service_name>_layer_summary.csv` | `~/Documents/arcgis_export/` |
| Metadata_Report.py | `item_inventory.csv` | `~/Documents/` |
| User_Reports.py | `user_inventory.csv` | `~/Documents/` |
| CSV_Mergeing_tool.py | User-specified | User-specified |

All output paths can be changed by editing the `OUTPUT_FILE_PATH` (or `OUTPUT_DIR`) variable near the top of each script.

---

## Authentication Options

The portal-based scripts all connect via `GIS('pro')` by default, which uses the active ArcGIS Pro session — no credentials are stored in the scripts.

To target a different portal, replace the connection line near the top of any script:

```python
# Default — uses ArcGIS Pro's active sign-in
gis = GIS('pro')

# ArcGIS Notebook hosted inside a portal
gis = GIS('home')

# Explicit Enterprise portal URL (prompts for credentials if needed)
gis = GIS("https://your-enterprise.com/portal")
```

For `List_of_all_services_in_the_REST.py`, which uses direct HTTP requests rather than the ArcGIS API, authentication is resolved in this order:

1. `ARCGIS_TOKEN` environment variable
2. ArcGIS Pro sign-in token via `arcpy.GetSigninToken()`
3. Interactive username/password prompt (generates a token automatically)

---

## Known Issues / Work in Progress

- **User_Reports.py** — Storage columns (`storage_usage`, `storage_quota`) can be difficult to interpret; the values are in bytes and the relationship between per-user quota and org-level quota is not always clear. Additionally, printing each user's information to unique, clearly labeled columns is a planned improvement.

---
## Publish_to_Federated_Server.py

**What it does:** Publishes an ArcGIS Pro map to a federated ArcGIS Server as both a **Map Image Service** and an **editable Feature Service**, while referencing a registered Enterprise Geodatabase (no data is copied to the server).

Unlike the built-in **Share as Web Layer** wizard, this script automates the entire publishing workflow, including enabling Feature Access, organizing Portal content, deleting temporary staging artifacts, and protecting the published services from accidental deletion.

### Workflow

The script performs the following steps:

1. Connects to the active ArcGIS Enterprise portal using the current ArcGIS Pro login.
2. Opens an ArcGIS Pro project (`.aprx`) and locates the specified map.
3. Creates a Service Definition Draft (`.sddraft`) targeting a federated ArcGIS Server.
4. Modifies the `.sddraft` XML to enable the **FeatureServer** extension with full editing capabilities.
5. Stages the draft into a Service Definition (`.sd`) file.
6. Uploads the `.sd` file to Portal.
7. Publishes the service to the federated ArcGIS Server.
8. Automatically:
   - Deletes the temporary Service Definition Portal item.
   - Moves the Map Service and Feature Service Portal items into the configured folder.
   - Enables delete protection on both Portal items.
9. Deletes the temporary local `.sddraft` and `.sd` files.

### Why Use This Script?

Although ArcGIS Pro includes a **Share as Web Layer** wizard, several important administrative tasks must still be completed manually when publishing to a federated ArcGIS Server.

This script automates those tasks by:

- Enabling Feature Access through XML modification.
- Publishing by reference to registered Enterprise Geodatabase data.
- Automatically deleting temporary Service Definition items after publishing.
- Organizing Portal items into the desired folder.
- Enabling delete protection on published services.
- Providing a repeatable deployment workflow using a single configuration section.

### Configuration

Edit the configuration block near the top of the script before running.

| Setting | Description |
|---------|-------------|
| `APRX_PATH` | Path to the ArcGIS Pro project (.aprx). |
| `MAP_NAME` | Name of the map to publish. |
| `SERVICE_NAME` | Name of the published service. |
| `SERVER_URL` | Federated ArcGIS Server REST URL. |
| `SERVER_FOLDER` | ArcGIS Server folder for the service. |
| `PORTAL_FOLDER` | Destination Portal content folder. |
| `SD_FOLDER` | Local folder for temporary staging files. |
| `SERVICE_SUMMARY` | Summary shown in Portal. |
| `SERVICE_TAGS` | Comma-separated Portal tags. |

### Requirements

- ArcGIS Pro 2.9 or later
- ArcGIS Enterprise / ArcGIS Server 10.9.1 or later
- ArcGIS API for Python
- Active Portal sign-in inside ArcGIS Pro
- Portal Administrator (or equivalent publishing privileges)
- Registered Enterprise Geodatabase data store on the federated server

### Notes

- References registered Enterprise Geodatabase data (**no data is copied to the server**).
- Automatically removes temporary `.sd` upload items from Portal after publishing.
- Moves the published Map Service and Feature Service items into the configured Portal folder.
- Enables delete protection on both Portal items to help prevent accidental removal of production services.
- Includes extensive inline comments documenting each stage of the publishing workflow, making it suitable as both a deployment tool and a learning resource for ArcGIS Enterprise automation.

---
## Credits and License

**Jonathan Kolterman** (2026)
[jkolterman13@gmail.com](mailto:jkolterman13@gmail.com) · [LinkedIn](https://www.linkedin.com/in/jonathan-kolterman-1808342b8)
