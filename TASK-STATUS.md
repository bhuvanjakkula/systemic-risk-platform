# Task status — September 25, 2026

## Completed and verified locally
- Existing ingestion, intelligence, digital twin, transparency demo and governance API.
- Website dashboard with baseline/stressed scans and JSON export.
- Interactive AI/no-AI twin comparison.
- Asymmetric loss and fiscal/moral-hazard cost scenario engine.
- Probability uncertainty and evidence/commitment/eligibility review gates.
- Cost-optimal cutoff selection on labeled validation predictions, Brier diagnostics,
  reliability bins, and explicit never-alert candidate.
- Normalized report CSV validation and LCR/capital-to-RWA arithmetic.
- Local launch scripts and documented operating instructions.
- 47 existing tests and 6 new workbench tests passed.

## Partial implementations, not production claims
- Signalling/commitment: evidence and commitment scenario gates implemented;
  no incentive-compatible mechanism or equilibrium solver has been validated.
- Cost curves: illustrative input costs and linear loss model implemented;
  hyperelastic/dynamic welfare models and institution-specific calibration remain.
- Signal-to-protocol mapping: review recommendations implemented; authenticated
  reviewer workflow and legally authorized intervention integration remain.
- Report ingestion: normalized CSV adapter implemented; official call-report field
  mapping and a live source connector remain pending a selected jurisdiction/feed.
- Model governance: existing monitors plus validation diagnostics; independent
  calibration data, model registry, approval lifecycle and drift baselines remain.

## External dependencies / unfinished production work
- Audited zk-SNARK proving circuit for LCR and CET1: not implemented or audited.
  Requires precise asset eligibility/RWA definitions, commitment linkage, a selected
  proof system, security review, and independent circuit audit. Existing proof is
  explicitly only a demonstration consistency check.
- Confidential ingestion: authenticated institutional endpoints, encryption key
  custody, retention rules and real-data integration remain unimplemented.
- Federated learning / MPC: requires participating institutions, threat model,
  protocol selection and secure deployment; no claim of confidential computation.
- Identity/access: requires identity provider, role policy and authenticated audit
  trail. Current website is a single-user local research service.
- Legal reporting standard: requires jurisdiction, reporting authority and legal
  review; the CSV schema is not a regulatory standard.
- Production supervisory readiness: no certification, external validation, secure
  multi-user operations, HA, persistent attestation ledger or incident exercises.

These dependencies mean that not all of yesterday's production requests are complete.
No actual intervention, liquidity transfer, or regulatory submission is performed.

## Local account access added
- Mobile/password sign-up, sign-in, and sign-out implemented.
- Server-side protection for the dashboard, API routes, and API documentation.
- Salted scrypt password storage, hashed expiring sessions, cross-origin request
  protection, persistent rate limiting, and authentication regression tests.
- Institutional SSO, role authorization, SMS verification, password recovery,
  and production identity review remain pending.

## Customer plans layer added
- Professional: USD 199/month; Bank: USD 899/month.
- Persistent per-account plan choice between sign-in and dashboard.
- No payment collection or active subscriptions; both choices currently open
  the same local research prototype. Billing integration remains pending.

## September 26 completion
- Completed the two interrupted requests: bank-focused first-page heading and email sign-up/sign-in.
- Preserved mobile login, plan selection, and reserved free owner access.
- Email ownership verification and recovery need a configured delivery provider; production dependencies above remain open.

