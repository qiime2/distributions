# Pull Request Template Guidelines
Below are a few examples of the information that should be included under each section of the PR template.

## DESCRIPTION

- Adds a new parameter to an existing action.
- Fixes #123.

## AI DISCLOSURE

- [ ] NO AI USED.
- [x] AI USED.

## AI USAGE DETAILS

- Codex (GPT-5.5) was used to draft the initial implementation; I refined the method and added testing/validation.
- Claude (Opus 4.7) was used to generate unit tests and refine docstrings.

------------------

*Please note that our CI system's linter will do a check for content in DESCRIPTION, exactly one checked box under AI DISCLOSURE, and content under AI USAGE DETAILS (only if AI USED was checked); these checks will fail if any of the above requirements are not met. The linting check can be re-run at any point during the PR's life cycle; this information only needs to be completed in full with the lint check passing prior to merge.*
