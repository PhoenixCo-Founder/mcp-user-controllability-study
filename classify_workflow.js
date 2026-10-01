export const meta = {
  name: 'mcp-user-controllability-classify',
  description: 'Classify 1347 MCP servers on 6 user-controllability dimensions (evidence-required) + 40-repo blind verification',
  phases: [
    { title: 'Classify', detail: '68 batches x ~20 repos, Sonnet subagents, evidence quotes required', model: 'sonnet' },
    { title: 'Verify', detail: '40-repo independent blind re-classification, disagreement rate', model: 'sonnet' },
  ],
}

const BASE = 'projects/seo-aeo/research-mcp-user-controllability'

const RUBRIC = `You are classifying a Model Context Protocol (MCP) server repository on 6 USER-CONTROLLABILITY dimensions. This is STATIC ANALYSIS of DOCUMENTED capability only (README + top-level file names). You measure what the docs describe, NOT runtime behavior.

CRITICAL RULES:
- Every label MUST be justified by a DIRECT QUOTE from the README, or by a specific filename from the "files" list. Put that quote/filename in the "evidence" field.
- If the docs do not contain enough information to determine a dimension, you MUST use label "insufficient_data" and explain in evidence what was missing. NEVER guess. NEVER infer from the repo name alone.
- Keyword matching is NOT sufficient. Filesystem "scope", data "scope", or code "scope" is NOT auth scoping. A "PRIVATE_KEY" for a crypto wallet is a static key. Read for MEANING.
- Judge the AUTH/CREDENTIAL path a human uses to connect an agent to this server, not the server's business domain.

THE 6 DIMENSIONS AND ALLOWED LABELS:

1. credential_delivery — How does a credential reach the server?
   - env_var_static_key: a static API key/token/secret set via environment variable (e.g. \`API_KEY\`, \`export FOO_TOKEN=\`)
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

Return one classification object per repo, in the SAME ORDER as the input, with all 6 dimensions. Do not skip any repo.`

const DIM_LABELS = {
  credential_delivery: ['env_var_static_key','config_file','oauth_redirect','user_mediated','none_needed','insufficient_data'],
  scoping_granularity: ['all_or_nothing','per_user','per_tool','per_action','user_selected_scope','none','insufficient_data'],
  revocability: ['documented_revocation','shared_key_rotation_only','redeploy_only','none','insufficient_data'],
  credential_lifetime: ['long_lived_static','expiring','user_chosen_duration','none','insufficient_data'],
  consent_surface: ['connection_time_approval','agent_reachable_consent','none','insufficient_data'],
  attribution: ['per_user_agent_attribution','shared_identity','insufficient_data'],
}

function dimSchema(labels) {
  return {
    type: 'object',
    properties: {
      label: { type: 'string', enum: labels },
      evidence: { type: 'string', description: 'Direct quote from README or a filename justifying the label; if insufficient_data, explain what was missing.' },
    },
    required: ['label', 'evidence'],
    additionalProperties: false,
  }
}

const REPO_SCHEMA = {
  type: 'object',
  properties: {
    repo: { type: 'string' },
    credential_delivery: dimSchema(DIM_LABELS.credential_delivery),
    scoping_granularity: dimSchema(DIM_LABELS.scoping_granularity),
    revocability: dimSchema(DIM_LABELS.revocability),
    credential_lifetime: dimSchema(DIM_LABELS.credential_lifetime),
    consent_surface: dimSchema(DIM_LABELS.consent_surface),
    attribution: dimSchema(DIM_LABELS.attribution),
  },
  required: ['repo','credential_delivery','scoping_granularity','revocability','credential_lifetime','consent_surface','attribution'],
  additionalProperties: false,
}

const BATCH_SCHEMA = {
  type: 'object',
  properties: { classifications: { type: 'array', items: REPO_SCHEMA } },
  required: ['classifications'],
  additionalProperties: false,
}

const NBATCHES = 68

// ---------- PHASE 1: CLASSIFY ----------
phase('Classify')
const batchResults = await parallel(
  Array.from({ length: NBATCHES }, (_, i) => () =>
    agent(
      `${RUBRIC}\n\nRead the file ${BASE}/batches/compact/${String(i).padStart(3,'0')}.json — it is a JSON array of repo records, each with {repo, stars, lang, readme (truncated), files (top-level filenames)}. Classify EVERY repo in the array on all 6 dimensions. Return one object per repo in the "classifications" array, same order as input. Evidence quotes are MANDATORY for every label.`,
      { label: `classify:${String(i).padStart(3,'0')}`, phase: 'Classify', model: 'sonnet', schema: BATCH_SCHEMA }
    ).then(r => ({ batchIdx: i, classifications: (r && r.classifications) || [] }))
  )
)

// Flatten, tagging each classification with its batch so verifiers can re-read the source.
const flat = []
for (const br of batchResults.filter(Boolean)) {
  for (const c of br.classifications) flat.push({ ...c, _batchIdx: br.batchIdx })
}
log(`Classified ${flat.length} repos across ${batchResults.filter(Boolean).length}/${NBATCHES} batches`)

// ---------- PHASE 2: VERIFY (40-repo blind re-classification) ----------
phase('Verify')
// Deterministic even spread of 40 samples across the flat list (no RNG available in scripts).
const N = flat.length
const SAMPLE = 40
const step = Math.max(1, Math.floor(N / SAMPLE))
const sampleIdx = []
for (let k = 0; k < N && sampleIdx.length < SAMPLE; k += step) sampleIdx.push(k)

const DIMS = Object.keys(DIM_LABELS)
const verifyResults = await parallel(
  sampleIdx.map(k => () => {
    const orig = flat[k]
    return agent(
      `${RUBRIC}\n\nRead the file ${BASE}/batches/compact/${String(orig._batchIdx).padStart(3,'0')}.json (a JSON array of repo records). Find the SINGLE record whose "repo" equals exactly "${orig.repo}" and classify ONLY that one repo on all 6 dimensions. Ignore all other records. Evidence quotes are MANDATORY.`,
      { label: `verify:${orig.repo.slice(0,28)}`, phase: 'Verify', model: 'sonnet', schema: REPO_SCHEMA }
    ).then(v => {
      if (!v) return null
      const perDim = {}
      let agree = 0
      for (const d of DIMS) {
        const a = orig[d] && orig[d].label
        const b = v[d] && v[d].label
        const same = a === b
        if (same) agree++
        perDim[d] = { orig: a, verify: b, agree: same }
      }
      return { repo: orig.repo, agreements: agree, total: DIMS.length, perDim }
    })
  })
)

const vr = verifyResults.filter(Boolean)
const totalCells = vr.length * DIMS.length
const agreeCells = vr.reduce((s, r) => s + r.agreements, 0)
const perDimDisagree = {}
for (const d of DIMS) {
  const dis = vr.filter(r => !r.perDim[d].agree).length
  perDimDisagree[d] = { disagreements: dis, of: vr.length, rate: vr.length ? +(dis / vr.length).toFixed(3) : null }
}

const verification = {
  sampled: vr.length,
  cell_agreement_rate: totalCells ? +(agreeCells / totalCells).toFixed(3) : null,
  cell_disagreement_rate: totalCells ? +(1 - agreeCells / totalCells).toFixed(3) : null,
  per_dimension_disagreement: perDimDisagree,
  full_agreement_repos: vr.filter(r => r.agreements === DIMS.length).length,
  details: vr,
}
log(`Verify: cell disagreement ${verification.cell_disagreement_rate}, ${verification.full_agreement_repos}/${vr.length} repos fully agreed`)

return { classifications: flat, verification }
