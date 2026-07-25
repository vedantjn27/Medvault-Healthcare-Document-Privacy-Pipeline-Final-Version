# MedVault — Frontend

The MedVault frontend is a TanStack Start + React 19 + Tailwind v4 app that talks to the
MedVault FastAPI backend. It ships every feature described in
`FRONTEND_IMPLEMENTATION_SPEC.md`: authentication, single-document workflow (upload →
preview → mode config → run → status polling → actual before/after preview → report → heatmap → feedback → session
download), mode comparison, batch processing, audit trail + integrity verification,
browser push notifications, and a session-scoped activity index.

> "Privacy is not a barrier to progress. It is the foundation of trust in healthcare."

## Requirements

- Node.js 20+ and npm 10+
- A running MedVault FastAPI backend

## Setup

```bash
cp .env.example .env
# Edit .env:
#   VITE_API_BASE_URL=http://localhost:8000
#   VITE_VAPID_PUBLIC_KEY=<same value as backend VAPID_PUBLIC_KEY>

npm install
npm run dev
```

## Environment variables

| Variable | Purpose |
| -------- | ------- |
| `VITE_API_BASE_URL` | Backend origin. `/api/v1` is appended automatically. Defaults to `http://localhost:8000`. |
| `VITE_VAPID_PUBLIC_KEY` | Public VAPID key used to subscribe to Web Push. Must match backend. |

### Environment-specific API origins

- `frontend/.env` is used by `npm run dev` and points to the local backend: `http://127.0.0.1:8000`.
- `frontend/.env.production` is used by `npm run build` and points to the deployed Render backend: `https://medvault-healthcare-document-privacy.onrender.com`.

Vite embeds `VITE_*` values at build time. Rebuild/redeploy the frontend after changing a production value. Configure `VITE_VAPID_PUBLIC_KEY` in the deployment provider's production environment variables when browser push is enabled.

## Scripts

```bash
npm run dev       # dev server
npm run build     # production build
npm run preview   # serve production build locally
```

## Architecture

- **API client** (`src/lib/api/client.ts`) — single typed fetch wrapper, snake_case
  fields preserved, centralized `401` → logout, XHR upload progress.
- **Auth** (`src/lib/auth/auth-context.tsx`) — token in memory + `sessionStorage`,
  expires-in watchdog, `getUser` restore, no refresh tokens.
- **Theme** (`src/lib/theme/theme-provider.tsx`) — light/dark toggle persisted in
  `localStorage`, respects `prefers-color-scheme`.
- **Session activity** (`src/lib/session/activity-store.ts`) — safe IDs and safe
  metadata only, cleared on logout, never contains PHI.
- **Push service worker** (`public/sw.js`) — `push` + `notificationclick` handlers,
  navigates to `/app/jobs/:jobId` when a payload provides one.

Sensitive previews, redaction reports, downloaded blobs, and heatmap object URLs
stay in memory. Object URLs are revoked on unmount / logout. `sessionStorage`
only holds the auth token, expiry, `User`, and the activity index.

## Routes

| Route | Purpose |
| ----- | ------- |
| `/` | Branding page (public). |
| `/auth/login`, `/auth/register` | Authentication. |
| `/app` | Dashboard with session-scoped activity. |
| `/app/upload` | Single-document upload. |
| `/app/documents/:documentId` | Preview + mode configuration + run redaction. |
| `/app/jobs/:jobId` | Status polling, actual before/after output preview, report, heatmap, feedback, and repeat downloads during the active session. |
| `/app/compare` | Two-to-five standard mode comparison. |
| `/app/batch` and `/app/batch/:batchId` | Batch upload + status + one-time ZIP. |
| `/app/audit` | Audit trail + integrity verification. |
| `/app/settings` | Browser push subscription. |
| `/app/contact` | Contact and environment help. |

## Contact

- Email: [vedantjain273@gmail.com](mailto:vedantjain273@gmail.com)
- LinkedIn: [Vedant Jain](https://www.linkedin.com/in/vedant-jain-858348318)
