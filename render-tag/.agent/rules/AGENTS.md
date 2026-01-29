# Agent Rules

Always maintain high code quality.

1. **Lint and Format**: Before finishing any coding task, run the lint and format workflow:
   ```bash
   # Run workflow: /lint_code
   ```
   Fix any errors reported by the tool.

2. **Type Check**: verify your type safety:
   ```bash
   # Run workflow: /type_check
   ```
   Ensure `ty` reports no errors.
