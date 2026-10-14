# Network Triage Dashboard (React + TypeScript + Vite)

React UI for the Network Bug Triage & Remediation Platform. It talks to the FastAPI
backend (`main.py` in the repo root) and shows telemetry events, triage decisions,
AI incidents, the remediation audit trail, and the human-approval workflow.

## Getting started

1. Start the backend from the repo root: `python main.py` (serves `http://127.0.0.1:8000`).
2. Install and run the UI:

```bash
npm install
npm run dev      # http://localhost:5173
```

| Script | Purpose |
|--------|---------|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-check (`tsc -b`) and production build |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run Oxlint |

## Configuration

`.env` sets the backend URL (defaults to `http://127.0.0.1:8000` if unset):

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The backend allows CORS from `localhost`/`127.0.0.1` on ports 3000, 5000, 5173 and 8000;
add others with the `NBT_CORS_ORIGINS` environment variable.

## Structure

- `src/pages/` - Overview, Events, Decisions, Incidents, Incident detail, AI Analysis, Remediation, Audit Trail
- `src/components/` - Sidebar, Topbar, Toast, action modals
- `src/services/api.ts` - API client for the `/api/*` endpoints
- `src/types/index.ts` - shared TypeScript types

## Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
