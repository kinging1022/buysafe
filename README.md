# buysafe

## Pre-launch mode

Until launch, the public site is a single waitlist page
(`frontend/src/views/PrelaunchView.vue`, from `frontend/design/prelaunch.reference.html`).
One build-time flag switches it:

| `VITE_PRELAUNCH` | `/` serves | Other URLs |
|---|---|---|
| `true` | the pre-launch waitlist page | redirect to `/` (keeping `?utm_…`), except `/login` and `/reset-password` for staff |
| anything else | the full landing page | the full site |

Production builds read `frontend/.env.production`, which sets `VITE_PRELAUNCH=true`.
`npm run dev` serves the full site; to see the pre-launch page locally, run
`VITE_PRELAUNCH=true npm run dev` (or put it in `frontend/.env.local`).

**Going live:** set `VITE_PRELAUNCH=false` in `frontend/.env.production` (or in the
deploy environment, which overrides the file) and rebuild. The head tags in the
built `index.html` follow the flag too.

Other frontend env vars (all optional; see `frontend/.env.example`):

- `VITE_CONTACT_EMAIL`: footer email link. Hidden when empty.
- `VITE_INSTAGRAM_HANDLE`: footer Instagram link (with or without `@`). Hidden when empty.

The PS5 photo goes at `frontend/src/assets/prelaunch/ps5.jpg`. Without it, the card
shows "PlayStation 5 Slim" in the photo well.

### The waitlist

Sign-ups go to `POST /api/waitlist/` (`backend/apps/waitlist`). Each phone number is
stored once as `+234…`; signing up again updates the state and role. The endpoint
replies `200 {"ok": true}` either way, so it never reveals who is on the list.
It is throttled per IP (5/min, 30/day, `waitlist` scopes in settings) and has a
`company` honeypot.

- **See demand:** Django admin → Waitlist signups. The "Signups by state" table
  above the list follows the filters (state, role, notified) and the search
  (`0803 123 4567` works).
- **Export:** select rows (or "Select all"), choose **Export selected signups as CSV**, then Go.
- **Launch SMS:** not built. `notified_at` is there for a Termii job to set once
  it has texted a number.

Behind a proxy, set DRF's `NUM_PROXIES` so the throttle sees the client IP rather
than the proxy's.

Tests: `cd backend && venv/bin/python manage.py test apps.waitlist`, and
`cd frontend && npm test`.
