# Classification rubric

This is the exact prompt text given to the classifier for every row (July 13, 2026 rubric with per-label definitions, plus the JSON output-format block). It is printed by `python3 rubric_detailed.py`, which reads it verbatim from `classify_workflow.js`. The repository records are appended after the last line.

```text
You are classifying a Model Context Protocol (MCP) server repository on 6 USER-CONTROLLABILITY dimensions. This is STATIC ANALYSIS of DOCUMENTED capability only (README + top-level file names). You measure what the docs describe, NOT runtime behavior.

CRITICAL RULES:
- Every label MUST be justified by a DIRECT QUOTE from the README, or by a specific filename from the "files" list. Put that quote/filename in the "evidence" field.
- If the docs do not contain enough information to determine a dimension, you MUST use label "insufficient_data" and explain in evidence what was missing. NEVER guess. NEVER infer from the repo name alone.
- Keyword matching is NOT sufficient. Filesystem "scope", data "scope", or code "scope" is NOT auth scoping. A "PRIVATE_KEY" for a crypto wallet is a static key. Read for MEANING.
- Judge the AUTH/CREDENTIAL path a human uses to connect an agent to this server, not the server's business domain.

THE 6 DIMENSIONS AND ALLOWED LABELS:

1. credential_delivery — How does a credential reach the server?
   - env_var_static_key: a static API key/token/secret set via environment variable (e.g. `API_KEY`, `export FOO_TOKEN=`)
   - config_file: credential placed in a config/JSON/yaml file (e.g. claude_desktop_config.json, .env file, smithery.yaml)
   - oauth_redirect: OAuth 2.0 / OIDC browser redirect flow to obtain a token
   - user_mediated: an explicit per-request or per-session human approval mediates access (not just setting a value once)
   - none_needed: server needs no credential (public data, local-only compute)
   - insufficient_data

2. scoping_granularity — Can the USER choose how narrow the grant is?
   - all_or_nothing: one key/token grants full access, no user-selectable narrowing
   - per_user: distinct credentials/identities per end-user
   - per_tool: access can be limited to specific tools
   - per_action: access limited per action/operation
   - user_selected_scope: user explicitly picks scopes/permissions at grant time (e.g. OAuth scopes the user consents to)
   - none: no auth so scoping is N/A but note it
   - insufficient_data

3. revocability — Can a user end THIS agent's access without rotating a shared key or redeploying?
   - documented_revocation: docs describe a revoke/disconnect path for an individual grant
   - shared_key_rotation_only: the only way to cut access is rotating a shared key (affects everyone)
   - redeploy_only: must change config and restart/redeploy
   - none: no described way to revoke
   - insufficient_data

4. credential_lifetime — How long does the credential live?
   - long_lived_static: static key with no expiry
   - expiring: token expires (fixed TTL, refresh tokens)
   - user_chosen_duration: user picks the lifetime
   - none: no credential
   - insufficient_data

5. consent_surface — Is there a human approval step at connection time, and is it reachable from the agent's own execution context?
   - connection_time_approval: a human approves at connect time (e.g. OAuth consent screen)
   - agent_reachable_consent: the consent step is reachable/operable from within the agent's execution context
   - none: no approval step; access is implicit once configured
   - insufficient_data

6. attribution — Does the server distinguish WHICH user/agent a call came from?
   - per_user_agent_attribution: calls are attributable to a specific user/agent identity
   - shared_identity: all calls share one identity (one key = one caller)
   - insufficient_data

Return one classification object per repo, in the SAME ORDER as the input, with all 6 dimensions. Do not skip any repo.

OUTPUT FORMAT: Return a JSON object with a "classifications" array. Each element has:
{
  "repo": "owner/name",
  "credential_delivery": {"label": "...", "evidence": "..."},
  "scoping_granularity": {"label": "...", "evidence": "..."},
  "revocability": {"label": "...", "evidence": "..."},
  "credential_lifetime": {"label": "...", "evidence": "..."},
  "consent_surface": {"label": "...", "evidence": "..."},
  "attribution": {"label": "...", "evidence": "..."}
}

Classify EVERY repo in the input array. Evidence is MANDATORY.

INPUT (JSON array of repos with readme and files):

```
