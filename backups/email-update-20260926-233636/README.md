# Systemic Risk Platform (prototype)

Four layers in one codebase:

1. Intelligence engine (features, isolation forest, contagion graph, ranked actions)
2. Digital twin (depositors + social amplification + AI herding)
3. Transparency (Merkle book + demonstration solvency attestation on an in-memory hash chain)
4. Governance monitors (vendor concentration, reporting z-scores, model-risk delta)

## Run

Use Python 3.12 for the pinned dependency stack.

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. python demo.py
PYTHONPATH=. uvicorn src.api.app:app --reload
```

In another activated terminal, run the tests:

```bash
PYTHONPATH=. pytest -q
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python demo.py
python -m uvicorn src.api.app:app --reload
```

In another activated terminal, run `python -m pytest -q`.
For runtime dependencies only, install `requirements.txt`.
The existing `python -m unittest discover -s tests -v` command also runs all tests.

## API

Open http://127.0.0.1:8000/docs for interactive documentation.

- `GET /health`: health and ledger height.
- `GET /scan?stressed=true&seed=7`: synthetic bank snapshots and alerts.
- `POST /twin`: compare AI-enabled and disabled scenarios. Accepts `seed`, `stressed`, `shocked_bank`, `rumor` (0 to 1), and `ai_agents`; `selected_scenario` identifies the requested mode.
- `POST /solvency/B01?stressed=true`: create and record a demonstration attestation.

`python -m src.api` also starts the API on the loopback interface.

## Prototype scope

Data is synthetic and model parameters are illustrative. The solvency module discloses aggregate totals and checks their consistency; it is not a zero-knowledge proof and does not establish that totals match the committed book. `verified: true` does not certify solvency. The ledger has no authentication, permission enforcement, signatures, consensus, or persistence. Run one worker; restarting clears the ledger.

Configuration is in `config/settings.yaml`. Missing files use built-in defaults; existing YAML is loaded without schema validation or default merging. The intelligence engine, twin, and governance modules use their respective settings; some threshold rules remain hard-coded in the supplied prototype.

## Local website (added September 25, 2026)

Double-click `Open-Website.cmd` to start the local server and open http://127.0.0.1:8010.
The server uses `.venv312` and binds only to loopback. Server output is in `server.log`
and `server-error.log`. Alternatively run:

```powershell
.\.venv312\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8010
```

The dashboard includes synthetic scans, JSON export, twin comparisons, policy loss
curves, validation-set threshold selection, and normalized report CSV import.
Imported reports are separate from synthetic scans and are not retained on disk.

New endpoints:
- `POST /policy/evaluate`: supplied probability and asymmetric costs, fiscal/moral
  hazard overhead, uncertainty interval, evidence/commitment/freshness/eligibility
  gates, and an audit value upper bound. Never authorizes financial execution.
- `POST /policy/calibrate`: labeled validation predictions, minimum empirical loss
  cutoff, Brier score, and reliability bins. It does not fit a calibrated model.
- `POST /reports/import`: JSON containing `csv`. Columns must be exactly
  `bank_id,as_of,currency,liquid_assets,stressed_outflows,capital,rwa`.
  Positive denominators, finite nonnegative amounts, ISO dates, and unique
  bank/date/currency tuples are required. Currency codes are syntax-checked only.

Policy formula: expected action loss = (1-p)*FP + p*TP + fiscal + moral hazard;
expected inaction loss = (1-p)*TN + p*FN. The crossing is
(FP-TN+fiscal+moral hazard)/(FP-TN+FN-TP). Reversed, constant, and dominated
policies are handled by directly comparing losses. Costs are illustrative inputs,
not empirically estimated welfare losses. Evidence checkboxes are scenario inputs,
not authenticated approvals. Policy hashes provide reproducibility, not signatures.

Threshold evaluation separates prediction from decision costs, following the
[scikit-learn cost-sensitive learning example](https://scikit-learn.org/1.6/auto_examples/model_selection/plot_cost_sensitive_learning.html).
Do not tune and report performance on the same final test set. Scan risk scores
remain heuristics and are never automatically treated as calibrated probabilities.

See `TASK-STATUS.md` for the remaining production dependencies.

## Mobile sign-up and sign-in

The first page now offers Sign in / Sign up using an international mobile number
and a 12–128 character password. Successful authentication opens `/dashboard`.
Dashboard APIs and API documentation require a valid session. `/health` remains
public for the launcher. Sign out invalidates the server-side session.

Accounts are stored in `data/accounts.sqlite3` under this non-OneDrive project.
Passwords use independently salted scrypt hashes (N=16384, r=8, p=5), following
[OWASP password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
Opaque session tokens are stored as hashes, expire after eight hours, and use
HttpOnly, SameSite=Strict cookies (Secure when served over HTTPS). Auth attempts
are limited per mobile number and client address over a 15-minute window.
The UI sends `X-SRP-Request: 1` on mutations; API clients must send it too.
Cross-origin mutations and unexpected hostnames are rejected.

Mobile numbers are identifiers only: no SMS verification or password-recovery
provider is configured. Accounts share the same synthetic research dashboard;
this is not institution-level authorization. The database is not encrypted at
rest. Keep this service on loopback; remote deployment requires HTTPS and a
reviewed account-verification, recovery, and authorization policy. Do not copy
`data/` into shared archives or source control.

Tests use a temporary database through `SRP_AUTH_DB` and do not create accounts
in your live local database.

## Customer plans

Account access now leads to `/plans` before the dashboard. Professional is
USD 199 per month; Bank is USD 899 per month. Each account's selection is stored
in `plan_preferences` in the local accounts database. Existing accounts are
preserved and choose a plan on their next visit. Authenticated customers can
change their choice using Customer plans in the dashboard.

This is a local plan-selection preview: no checkout, payment, recurring charge,
or active subscription is created. Both plans currently access the same research
prototype. Plan IDs and displayed monthly prices are fixed on the server;
clients cannot submit custom prices. An actual billing provider and verified
payment webhooks are required before granting paid subscription entitlements.

Endpoints: `GET /plans/catalog` (public), `GET /plans/current`,
`POST /plans/select` with `{"plan_id":"professional"}` or `{"plan_id":"bank"}`.
Selection requires authentication and the existing request-origin protection.

## Free local owner account

`bhuvanjakkula@gmail.com` is explicitly provisioned as this installation's owner.
It signs in using the email and a local project password, skips customer plan
selection, and has free access to all current dashboard tools. This is not Google
sign-in, mailbox verification, or a paid subscription. Customer sign-ups cannot
set the owner role or register an email through the mobile registration endpoint.

The owner first sets a password through a random, one-use setup link, valid for
24 hours. Only its SHA-256 hash is stored in SQLite; the link token stays in the
URL fragment and is sent only to the local setup endpoint. Completed setup
invalidates the token and signs in the owner. Never publish or share a live setup
link. The local `provision_owner()` administrative helper may issue a fresh link
for an unactivated account; it refuses to reset an activated account's password.
