# Repository Operating Rules

- Treat `PRODUCT.md` and the decisions in `docs/DECISIONS.md` as the source of truth.
- Follow all approved decisions in docs/DECISIONS.md. Consult the repository documentation for architecture details.
- Preserve the dependency direction API → Application → Domain; connect concrete infrastructure at the composition root.
- Keep financial logic out of UI components and HTTP handlers.
- Do not invent financial methodology. Financial functionality requires an approved methodology and automated tests.
- Add dependencies, abstractions, and infrastructure only for a concrete need.
- Never commit secrets, credentials, private keys, or sensitive real financial data.
- Before finishing, run the relevant lint, typecheck, test, and format checks.
- Use short-lived branches and pull requests for application-code changes.
