# Department Requirements and Integration Matrix

The official Sentinel material describes a multi-department, heterogeneous catalogue and a live/simulated feed set. The matrix below converts that into integration questions. “To confirm” means an external owner must supply the value; it is not silently assumed.

| Department / source | Expected integration | Required inputs | Output/acceptance evidence | Status |
|---|---|---|---|---|
| Police / traffic | Watchlist and investigation workflows | Camera catalogue, watchlists, escalation roles, evidence policy | Alert acknowledgement, audit, export and route history | `PARTIAL — owner confirmation required` |
| Health | Department camera feeds and access roles | Stream endpoints, retention, operators, network path | Feed health and least-privilege access | `PARTIAL — owner confirmation required` |
| GSRTC / transport | Depot, corridor, or bus-stand feeds | VMS protocol, camera metadata, operating windows | Designated-vehicle sightings and timestamps | `PARTIAL — owner confirmation required` |
| Panchayat / local bodies | Distributed low-bandwidth feeds | Gateway placement, connectivity, local storage | Store-and-forward and degraded-mode evidence | `PARTIAL — owner confirmation required` |
| Municipal corporation | Urban camera catalogue | GIS coordinates, codecs, retention, traffic peaks | Cross-camera chronology and department report | `PARTIAL — owner confirmation required` |
| State catalogue / GIS | Central registry and location source | Stable camera IDs, coordinates, departments, routes | Camera identity and feasibility inputs | `PARTIAL — official schema not supplied` |
| VMS/RTSP/WebRTC/HLS | Stream ingestion | RTSP/WHEP/HLS endpoint, auth, codec, time base | Connect/reconnect/epoch evidence | `READY FOR SANDBOX CONTRACT` |

## Deployment responsibility matrix

| Owner | Responsibility | Required inputs / acceptance | Dependency class |
|---|---|---|---|
| Police / Control Room | Register targets, review alerts, investigate sightings, acknowledge/escalate cases | Watchlist authority, severity policy, operator roles, investigation acceptance | `MANDATORY_FOR_PILOT` |
| CCTV / VMS Team | Maintain stream availability, IDs, timestamps, endpoint access and metadata | RTSP/HLS/WHEP access, codec, NTP/PTS behavior, maintenance contact | `MANDATORY_FOR_PILOT` |
| IT / Data Centre | Provide compute/GPU, containers/VMs, database, DNS, certificates, monitoring and backups | Approved topology, capacity-test hardware, PostGIS, secrets path, restore test | `MANDATORY_FOR_PRODUCTION` |
| Network Team | Provide VLAN/firewall routes, QoS, regional connectivity and WAN controls | Bandwidth, allowed ports, private routes, outage procedure | `MANDATORY_FOR_PILOT` |
| Cybersecurity | Govern IAM, secrets, RBAC, logs, vulnerability management and audit review | Security assessment, trust boundaries, rotation, incident response | `MANDATORY_FOR_PRODUCTION` |
| GIS / Mapping | Validate coordinates, junction metadata and camera geolocation | Authoritative GIS export, coordinate accuracy, correction workflow | `MANDATORY_FOR_PILOT` |
| Investigation / Operations | Govern watchlists, false-positive review, evidence handling and retention | Review SLA, legal hold, export format, training and acceptance owner | `MANDATORY_FOR_PILOT` |
| Procurement | Size hardware, warranty, support, spares and phased rollout | Vendor-neutral bill of quantities after qualification tests | `MANDATORY_FOR_PRODUCTION` |
| Legal / Privacy / Governance | Approve retention, access, audit, purpose and evidentiary policy | Written policy, data owner, deletion/legal-hold rules | `MANDATORY_FOR_PRODUCTION` |

## Required owner questionnaire

For every camera: stable ID, department, physical location, timezone, latitude/longitude accuracy, stream URL/protocol, codec/resolution/FPS/bitrate, credentials path, NTP/PTP status, retention owner, privacy zones, expected uptime, maintenance contact, and whether the feed may leave the department network.

For every department: roles, watchlist authority, alert severity policy, review SLA, evidence retention, legal hold, export format, deletion policy, incident contact, and acceptance test owner.

## Official alignment

The official FAQ describes 26 independent government departments, heterogeneous analog/IP sources, and a central registry/GIS requirement. The official resource guidance exposes RTSP, WHEP, HLS, and API-ingest patterns. Exact production catalogue schema, credentials, and department-level retention values were not published in the verified public material and remain `OFFICIAL_REQUIREMENT_NOT_VERIFIED` until supplied by the organizers or departments.
