# AI D&D Master frontend

Initial React, TypeScript, and Vite client for AI D&D Master.

The login page is presentation-only. The repository does not yet define an
authentication API, so submitting the form validates the fields and reports
that backend integration is pending; it does not send credentials anywhere.

## Requirements

Node.js 24.15.0 or newer within the Node 24 release line. This baseline is
compatible with Vite 8 and the current frontend development dependencies; it
is also used by frontend CI.

## Development

```bash
cd frontend
npm install
npm run dev
```

## Checks

```bash
npm run lint
npm run test
npm run build
```
