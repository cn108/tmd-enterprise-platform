# TMD Platform — frontend

Angular 22 workspace for the TMD internal portal.

**Phase 1 scope:** application shell only. It reports the backend's readiness status and states plainly that no business modules are enabled. There are no procurement, inventory, billing or ledger screens yet, because those depend on decisions still open in `../docs/13-decision-register.md`.

## Commands

```bash
npm ci                  # install exactly what CI installs
npm start               # dev server on http://localhost:4200
npm run build           # production build into dist/frontend
npm run lint            # ESLint (angular-eslint)
npm test -- --watch=false   # Vitest, headless
```

## API access

`proxy.conf.json` forwards `/api` to `http://127.0.0.1:8000`, so the browser makes same-origin requests and there is no CORS configuration to maintain. Start the Django backend before using the portal, or the status card will say the API is unreachable.

## Conventions

- Standalone components, signals for local state, typed reactive forms.
- Feature code goes in `src/app/<feature>/`; shared primitives in `src/app/core/`.
- The client never computes balances, prices, tax or journal amounts — the backend is the only authority.
- Do not add business screens before their phase is authorised in `../docs/14-backlog.md`.
