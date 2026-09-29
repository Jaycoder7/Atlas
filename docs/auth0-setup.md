# Auth0 production checklist

Atlas runs without Auth0 only when `ATLAS_AUTH_MODE=demo`. Never use demo mode in a shared or production environment.

1. Create a Regular Web Application and an API in Auth0. Use `https://api.atlas.local` (or your own value) as the API audience and RS256 signing.
2. Enable Auth0 Organizations. Add users to organizations and assign either the `admin` or `member` role.
3. Add an Auth0 Action that copies the assigned roles to the access-token claim `https://atlas.local/roles`. Human organization tokens must include the standard `org_id` claim.
4. Configure callback `/auth/callback`, logout URL `/`, and the deployment web origin. For local development these are rooted at `http://localhost:3000`.
5. Set `ATLAS_AUTH_MODE=auth0`, `NEXT_PUBLIC_AUTH_MODE=auth0`, `APP_BASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_SECRET`, `AUTH0_AUDIENCE`, and `AUTH0_ISSUER`.
6. Create a Machine-to-Machine Application for lab automation, authorize it for the Atlas API, and grant `test-results:write`.
7. As an Atlas administrator, register the M2M application's Auth0 client ID at `POST /api/v1/admin/service-clients`. This binds the client to exactly one organization; ingestion payloads cannot select a tenant.
8. Verify manually: human login, organization selection, admin-only service-client management, member CRUD access, cross-organization 404/403 behavior, M2M ingestion, token expiry, and logout.

The Next.js server acts as a token-mediating backend: browser requests use the same-origin `/api/atlas` proxy, and access tokens are attached server-side rather than exposed to client code.
