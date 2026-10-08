# Model 1 Camera Registry and GIS Gap Analysis

Snapshot: **2 September 2026, 14:42:06 UTC**

Evidence class: **local PostgreSQL/PostGIS registry snapshot**

Machine-readable evidence: [`CAMERA_GAP_ANALYSIS.json`](CAMERA_GAP_ANALYSIS.json)

## Answer first

The technical Model 1 workflow is implemented: an authorized supervisor or
administrator can manually register or edit a camera, dry-run and atomically
apply a CSV import, record coordinate provenance, export registry gaps and
GeoJSON, estimate planning coverage for an operator-supplied area, validate a
camera-to-camera time/distance hypothesis, and invoke two bounded VMS adapter
types. Mutations use RBAC, CSRF, database transactions, and audit logging.

The current 30-camera organizer registry does **not** contain authoritative GPS,
department, organization, or azimuth data. SentinelTrack therefore reports
those fields as missing. It does not turn textual place names into police-grade
coordinates by guessing or silent geocoding.

## Current registry evidence

| Check | Result | Interpretation |
|---|---:|---|
| Registered cameras | 30 | Persisted organizer camera definitions |
| Enabled for processing | 30 | Registry enablement; this is not an ONLINE claim |
| Cameras with a stream source | 30 | At least one RTSP or HLS URL is configured |
| Cameras with coordinates | 0 | Authoritative coordinate data has not been supplied |
| Verified coordinates | 0 | No survey provenance can currently be claimed |
| Missing department | 30 | Department ownership is an external metadata gap |
| Missing organization | 30 | Organization ownership is an external metadata gap |
| Missing azimuth | 30 | Directional coverage cannot yet be assessed |
| Source system identified | 30 | All current rows carry `SENTINEL_CATALOGUE` provenance after authenticated synchronization |

`isolated_camera_ids` is empty because no camera has a point geometry. It must
not be interpreted as evidence that every camera has a nearby neighbour.

The organizer session authenticated in the final doctor run and returned all
30 catalogue records. Earlier bounded attempts did time out, demonstrating that
host availability can fluctuate; failed refreshes did not erase the persisted
registry.

## Implemented gap-closing workflow

1. Open **Cameras → Camera setup and GIS**.
2. Use **Edit selected camera** to add WGS84 latitude/longitude, quality, and
   coordinate source to an existing organizer camera.
3. For an official spreadsheet, download the template, select **Import camera
   CSV**, run server validation, inspect every row, and only then choose **Apply
   validated import**.
4. Download **Gap report CSV** to return unresolved records to the GIS/VMS
   owners. Download **Camera map GeoJSON** for standards-compatible mapping.
5. After at least two camera locations exist, use **GIS demonstration** to
   calculate lower-bound distance, minimum required speed, and feasibility.
6. Paste an approved area-of-interest Polygon/MultiPolygon to obtain a bounded
   PostGIS planning-coverage estimate.

The tracked bulk template is
[`configs/camera_import_template.csv`](../../configs/camera_import_template.csv).
Imports are capped at 500 records and support `CREATE_ONLY` or explicit
`UPSERT`. Stream URLs containing embedded credentials and metadata containing
password/token/cookie keys are rejected.

## Heterogeneous integration evidence

| Adapter | Implemented contract | Evidence boundary |
|---|---|---|
| Organization A — OGC API Features | Reads a bounded GeoJSON `FeatureCollection`, normalizes Point geometry and camera properties, supports an environment-only bearer token | Contract tested; placeholder is disabled until a real department approves its endpoint and secret |
| Organization B — ONVIF Profile T | Discovers Device and Media/Media2 services, reads device/scopes/profiles, selects the highest-resolution profile, requests RTSP, and strips credentials from returned URLs | Contract tested; placeholder is disabled until a real device endpoint and credentials are supplied |

Both adapters disable redirects, bound response size and timeout, keep secrets
outside JSON, and send normalized records through the same audited bulk-import
contract. ONVIF service-discovery hosts are allowlisted to prevent an advertised
service URL from becoming an unrestricted server-side request.

Configuration lives in
[`configs/vms_connectors.json`](../../configs/vms_connectors.json). The two
entries are safe disabled templates, not fabricated live vendor integrations.

## GIS truth boundary

- GeoJSON uses WGS84/OGC:CRS84 coordinate order: longitude, latitude.
- Nearby and isolation checks use PostGIS geography distance.
- Route feasibility uses straight-line/geodesic distance as a lower bound.
- It is not road-network routing, map matching, traffic prediction, or proof of
  the path a vehicle took.
- Coverage uses circular buffers because calibrated lens/occlusion polygons are
  unavailable. It is explicitly labelled a planning approximation.

This conservative boundary follows the interface direction in
[OGC API – Features](https://ogcapi.ogc.org/features/index.html) and leaves a
future path to the 2025
[OGC API – Connected Systems](https://www.ogc.org/standards/ogc-api-connected-systems/)
standard for richer sensor deployments and dynamic observations. IP-camera
discovery follows [ONVIF Profile T](https://www.onvif.org/profiles/profile-t/),
which covers advanced IP video streaming including H.264/H.265 and metadata.

Recent camera-placement research frames placement as an optimization problem,
not a circle-counting shortcut. The current gap tool therefore does not claim
optimal placement. A future planning phase can build on Kumar, Bollapragada,
and Leibowicz (2024),
[“Efficient Mathematical Programming Formulation and Algorithmic Framework for
Optimal Camera Placement”](https://arxiv.org/abs/2411.17942), after roads,
occlusions, recognition range, costs, and candidate sites are supplied.

## Remaining ownership

The remaining gaps are external data/acceptance work, not missing code:

- GIS owner supplies and verifies coordinates and survey references.
- Each department supplies ownership, endpoint, codec, clock, and contact data.
- Security owner provisions secrets outside Git and approves connector hosts.
- Department/VMS owners perform live contract validation.
- Submission owner demonstrates onboarding and exports the resulting report in
  the final recording.

Until those inputs exist, the correct state is **UNKNOWN / setup required**, not
green fabricated completeness.
