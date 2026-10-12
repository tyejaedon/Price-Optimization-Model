# Protected pricing browser demo

This static page is a manual test client for an **already deployed, Firebase-protected** pricing
API. It is not an authentication provider and must not be pointed at the unauthenticated
`src.serve:app` local development entrypoint. It accepts a short-lived Firebase ID token supplied
by a tester, sends it only as `Authorization: Bearer …` for one quote, and clears the field after
the request. The token is not written to local storage, cookies, URLs, logs, or analytics.

Serve the static files from loopback:

```powershell
python -m http.server 4173 --bind 127.0.0.1 --directory demo
```

Open `http://127.0.0.1:4173`, enter the HTTPS staging API **origin** (no path), and use the profile
document ID owned by the Firebase identity represented by the test token. The tester must obtain a
short-lived ID token through the approved Firebase Auth test flow outside this page; do not paste
Firebase Admin credentials, service-account keys, production tokens, or participant data.

Configure the protected API with this exact origin in its runtime environment:

```text
PRICING_CORS_ALLOWED_ORIGINS=http://127.0.0.1:4173
```

The backend accepts only exact HTTPS origins, except HTTP loopback origins for local browser
testing. Wildcards, URL paths, credentials in origins, and non-loopback HTTP origins are rejected.
Credentialed browser requests and cookies are disabled; only GET/POST and the `Authorization` and
`Content-Type` headers are allowed. Configure only origins you control, and remove the loopback
origin from a staging deployment after testing.

The page uses `GET /health` and refuses to send a quote unless the API reports `HEALTHY`, loaded
models, and a Firestore repository. It then sends the canonical camelCase request to
`POST /api/v1/optimize-price`. The backend remains responsible for Firebase ID-token verification,
mentor ownership, request validation, and returning 401/403/422/503 errors; CORS is not
authentication. A missing or expired token is never replaced with a demo identity or bypass flag.

Use HTTPS for staging and production. Plain HTTP is accepted by the page only for loopback. Browser
CORS errors do not expose the server response; confirm the exact browser origin is configured in
`PRICING_CORS_ALLOWED_ORIGINS`.
