SAFEROUTE AI — WINDOWS 7 + ANDROID LOCAL DEMO
============================================

WHAT IS INCLUDED
- frontend/index.html: map, route comparison, nearby services, accident layers.
- backend/main.py: Flask API and SQLite database, including citizen-report moderation queue.
- backend/requirements.txt: Python packages.
- INSTALL_DEPENDENCIES.bat: installs the required Python packages.
- START_BACKEND.bat: starts the API server.
- START_FRONTEND.bat: starts the website server.

STEP 1 — INSTALL PYTHON
Read INSTALL_PYTHON_FIRST.txt. This old Windows 7 laptop needs Python 3.8.10, 32-bit.

STEP 2 — INSTALL APP PACKAGES
Double-click INSTALL_DEPENDENCIES.bat and wait until it says Installation complete.

STEP 3 — START THE BACKEND
Double-click START_BACKEND.bat. Enter a private admin key when prompted (use at least 20 characters and do not share it). Keep its black Command Prompt window open.
On the laptop, visit http://localhost:8000/health . You should see JSON with status "ok".

STEP 4 — START THE WEBSITE
Double-click START_FRONTEND.bat in a second Command Prompt window.
On the laptop, open http://localhost:5500

STEP 5 — OPEN ON ANDROID
Connect the phone and laptop to the SAME Wi-Fi network.
On the laptop, open Command Prompt and type: ipconfig
Find the Wi-Fi adapter's IPv4 Address (example: 192.168.1.10).
On Android Chrome, open http://LAPTOP-IP:5500 (replace LAPTOP-IP with that IPv4 address).
If Windows Firewall asks, allow Python on Private networks only.

IMPORTANT DATA LIMITATIONS
- The app does not contain a verified nationwide accident dataset by default. The historical layer will be empty until legitimate point-level records are imported.
- The live layer is a feed for reports entered by an authorised operator. It does not independently detect all accidents or connect to a national emergency feed.
- The example coordinates in API documentation are illustrative, not real accident reports.
- Nearby services and routes use external OpenStreetMap/OSRM services and require internet access. Coverage and routing can vary.
- A district/state accident count is not an exact map point. Only import records with genuine point coordinates and a named source.

SECURITY
This package is for a local classroom demonstration. Windows 7 and Python 3.8 are out of support. Do not expose this laptop/server directly to the public internet. Do not share the admin key. Before any real deployment, use a supported operating system, HTTPS, proper authentication, access controls, logging, backups and authorised data agreements.

IF SOMETHING FAILS
Take a clear photo of the full error in the Command Prompt and share it. Do not close the window before capturing the error.


OPTIONAL — LOAD THE PROVIDED SAMPLE DATA
1. Start the backend once, then close it.
2. Double-click IMPORT_SAMPLE_DATA.bat.
3. Restart the backend and refresh the website.
4. The records are clearly marked UNVERIFIED sample data.
Read DATA_QUALITY_AND_DEMO_GUIDE.txt before presenting this project.

CITIZEN REPORTING AND MODERATION
- The website has a report form. A citizen can enter a location or grant browser location permission, then submit a short road hazard/incident report.
- POST /api/reports stores the report as pending_review. It is NOT immediately shown on the public map.
- An authorised moderator can list pending reports using GET /api/admin/reports with the X-Admin-Key header.
- Approve: POST /api/admin/reports/<id>/approve with JSON {"source":"Moderator checked report"}.
- Reject: POST /api/admin/reports/<id>/reject with the X-Admin-Key header.
- Approval publishes a 24-hour reviewed incident. The moderator must independently check the report before approving it.
- This local demo has no rate-limiting or production-grade identity verification. Do not expose it publicly.
- Browser location permission works on localhost or a secure HTTPS website; some browsers block geolocation on plain local-network HTTP. Manual coordinates remain available.

DATA LABELS
- The supplied CSV remains UNVERIFIED sample data. The map and route indicator must not be described as official accident statistics or crash prediction.
- The route indicator counts proximity to loaded records only. It is not a validated probability or a guarantee of safety.
