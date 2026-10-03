---
name: authenticate-wallet
description: Authenticate to AgnicPay wallet using browser OAuth or non-browser API token mode
user-invocable: true
disable-model-invocation: false
allowed-tools: ["Bash(npx agnic@latest *)"]
---

# Authenticate Wallet

Authenticate the user with their AgnicPay wallet using browser OAuth or token-based auth for headless agents.

## Steps

1. Preferred for headless agents: provide a token (no browser required):
   ```bash
   npx agnic@latest --token <agnic_token> status --json
   ```
   Or set an environment variable:
   ```bash
   export AGNIC_TOKEN=<agnic_token>
   npx agnic@latest status --json
   ```

2. Browser mode: run the login command:
   ```bash
   npx agnic@latest auth login
   ```
   This opens the user's browser to AgnicPay where they sign in and set spending limits.

3. Wait for the browser flow to complete. The CLI will show "Authenticated!" when done.

4. Verify authentication:
   ```bash
   npx agnic@latest status --json
   ```

## Expected Output

```json
{
  "authenticated": true,
  "userId": "did:privy:...",
  "email": "user@example.com",
  "walletAddress": "0x...",
  "tokenExpiry": "2026-05-22T..."
}
```

## Error Handling

- If the user cancels the browser flow, the CLI will show "Authentication failed".
- If the browser doesn't open, the CLI prints a URL the user can copy manually.
- If token auth fails, check whether the token is valid/revoked/expired.
- If already authenticated, `agnic status` will confirm without re-login.

## Logout

To remove stored credentials:
```bash
npx agnic@latest auth logout
```
