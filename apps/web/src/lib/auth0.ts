import { Auth0Client } from "@auth0/nextjs-auth0/server";

const demoMode = process.env.ATLAS_AUTH_MODE !== "auth0";

export const auth0 = new Auth0Client({
  domain: demoMode ? "demo.invalid" : undefined,
  clientId: demoMode ? "atlas-demo" : undefined,
  clientSecret: demoMode ? "atlas-demo-not-used" : undefined,
  secret: demoMode ? "atlas-demo-secret-at-least-thirty-two-characters-long" : undefined,
  appBaseUrl: process.env.APP_BASE_URL || "http://localhost:3000",
  authorizationParameters: {
    audience: process.env.AUTH0_AUDIENCE,
    scope: "openid profile email offline_access",
  },
});

export const authEnabled = !demoMode;
