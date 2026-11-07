# Contributing

1. Write or update the relevant spec in `.kiro/specs/<feature>/` before building a major feature.
2. One feature per branch. Keep changes small and reviewable.
3. Run `make backend-lint backend-test` and `make frontend-check frontend-build` before opening a PR.
4. Never commit secrets. Never remove `.kiro/` from version control.
5. Update `BUILD_STATUS.md` honestly. Do not mark work VERIFIED without evidence.
