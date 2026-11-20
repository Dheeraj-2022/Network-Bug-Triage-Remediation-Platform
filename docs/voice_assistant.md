# Voice-First Operations Assistant (`controller/voice/`)

The optional voice-first operations assistant provides a **bounded, allowlisted, backend-authenticated** voice and text interface to existing platform capabilities. It is **not** an unrestricted autonomous agent.

## Allowlisted Operations

| Category | Intent | Required Role | Confirmation Required |
|---|---|---|---|
| Read-only | `server_status` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `recent_incidents` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `incident_evidence` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `server_topology` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `change_correlation` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `drift_findings` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `remediation_status` | `viewer`, `operator`, `senior_approver` | No |
| Read-only | `verification_result` | `viewer`, `operator`, `senior_approver` | No |
| Safe demo | `demo_load` | `operator`, `senior_approver` (with `gpu-a`/`gpu-b` scope) | No |
| Safe demo | `preview_remediation` | `viewer`, `operator`, `senior_approver` | No |
| Safe demo | `demo_reset` | `operator`, `senior_approver` (with `gpu-a`/`gpu-b` scope) | **Yes (readback + explicit confirm)** |
| State-changing | `approve_remediation` (simulated only) | `operator`, `senior_approver` | **Yes (readback + explicit confirm; step-up/second approver for high-risk)** |

**Disabled over voice in MVP (fail closed with HTTP 403):**
- Clearing all platform state (`/api/clear`)
- Driver restarts / kernel module reloads (`restart_driver`)
- Live infrastructure changes (`NBT_REMEDIATION_MODE=ansible`) or switch reconfigurations
- Arbitrary shell, SQL, Python, Ansible arguments, or external URLs

## Authentication, RBAC & Per-Host Scoping

- Every operational endpoint (`/api/voice/me`, `/api/voice/query`, `/api/voice/confirm`, `/api/voice/audit`) requires a backend-verified token via `X-Voice-Token` or `Authorization: Bearer <token>`.
- Voice recognition is **never** treated as identity verification.
- **Configured mode (recommended beyond local demo):** set `NBT_VOICE_USERS_JSON` (or `NBT_VOICE_USERS_FILE`) to a JSON array of `{token, user_id, display_name, role, allowed_hosts, step_up_code?}`. When configured, `/api/voice/demo-session` is disabled (HTTP 403).
- **Local demo mode:** when no configured voice users are set (and `NBT_VOICE_DEMO_PROFILES` is not `0`), `POST /api/voice/demo-session` issues an ephemeral random in-memory session token for one of four scoped profiles (`viewer-gpu`, `operator-gpu`, `operator-lab`, `senior-approver`). Tokens are stored only in `sessionStorage` and never bundled into Vite assets.

## Confirmation, Readback & Verification

1. State-changing voice requests return `status: "confirmation_required"` with a `confirmation_id` (120s TTL) and an exact `readback` naming the action, target host/interface, desired value, mode (`simulated`), risk, and `preview_digest`.
2. Confirming requires `POST /api/voice/confirm` with `confirm: true` (and an unambiguous phrase such as `"yes confirm"` if spoken). Silence, empty input, or ambiguous phrases (`"maybe"`) fail closed.
3. High-risk or shared-infrastructure operations require either a `senior_approver` `step_up_code` or a distinct `senior_approver` `second_approver_token`.
4. Approved remediations execute through the shared `RemediationPolicy`. The assistant never claims resolution unless the deterministic post-check returns `outcome == "passed"`.

## Speech Privacy & Data Handling

- **Optional browser speech:** The React UI uses the browser Web Speech API (`SpeechRecognition` / `speechSynthesis`) only when the user clicks *Speak*. Depending on the browser, audio may be sent to the browser vendor's speech recognition service.
- **Fully local text fallback:** Typing in the Voice Assistant page keeps all input strictly local between the browser and the FastAPI backend.
- **No raw audio retention:** The backend receives only text transcripts and never accepts or stores raw audio.
- **Secret redaction & prompt-injection defense:** Credentials, API keys, Bearer tokens, passwords, and private keys are redacted (`[REDACTED]`) from transcripts, responses, spoken text, and the SQLite audit log (`logs/voice_audit.sqlite3`, override with `NBT_VOICE_AUDIT_DB`). Instruction-like prompt-injection text in transcripts is refused; injection text in retrieved telemetry/logs is neutralized before surfacing.

## Tests

```bash
python3 -m unittest tests.test_voice_assistant -v
```
