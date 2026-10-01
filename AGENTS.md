# Repository Operating Rules

- Treat `PRODUCT.md` and the decisions in `docs/DECISIONS.md` as the source of truth.
- Follow all approved decisions in docs/DECISIONS.md. Consult the repository documentation for architecture details.
- Preserve the dependency direction API → Application → Domain; connect concrete infrastructure at the composition root.
- Keep financial logic out of UI components and HTTP handlers.
- Do not invent financial methodology. Financial functionality requires an approved methodology and automated tests.
- Require a Finance decision when financial meaning, recognition timing, allocation/accounting rules, currency interpretation, or missing-data financial treatment changes.
- Require an Architecture decision when durable module/public boundaries, the persisted model, major external contracts, or runtime/deployment direction changes.
- Development may decide helper placement, module extraction, ordinary queries, DTO mapping, component structure, risk-appropriate test organization, and internal refactoring that preserves approved semantics/contracts.
- Add dependencies, abstractions, and infrastructure only for a concrete need.
- Never commit secrets, credentials, private keys, or sensitive real financial data.
- Define milestones by user-visible product capability, not internal foundation completion. Use one final complete-capability review by default; intermediate reviews and focused re-reviews are for concrete high-risk uncertainties or blockers.
- Update documentation for durable rules or factual project status; do not create an ADR/Decision for an ordinary implementation detail.
- Before finishing, run the relevant lint, typecheck, test, and format checks appropriate to the actual change and risk.
- Use short-lived branches and pull requests for all changes, including documentation; never commit directly to protected main. Keep one coherent PR per meaningful capability and do not merge without explicit authorization.
