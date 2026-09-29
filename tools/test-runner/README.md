# Atlas test-result client

The simulator exercises the same authenticated endpoint intended for laboratory automation.

```bash
python3 simulate.py thermal-failure
python3 simulate.py passing-suite
```

In local demo mode no token is required. For Auth0 mode, provide `ATLAS_CLIENT_ID`, `ATLAS_CLIENT_SECRET`, `AUTH0_DOMAIN`, and `AUTH0_AUDIENCE`; the client obtains a machine-to-machine token before submission.

