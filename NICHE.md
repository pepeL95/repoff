You are working inside the `repoff` repository.

Repository-specific instructions:

- Treat coding requests as execution tasks by default. Inspect the repo, make the change, and verify it.
- Prefer the existing architecture: thin VS Code extension, backend-owned orchestration and policy.
- Do not introduce duplicate tool layers or broad new framework abstractions unless they are clearly necessary.
- Keep changes narrow and well-shaped. Put logic in the layer that owns it.
- Prefer simple, explicit object boundaries over helper sprawl or hidden shared state.
- If a request can be solved by extending an existing seam cleanly, do that instead of inventing a new subsystem.
- For codebase claims, read files or run commands before concluding.
- Keep final answers compact and practical.
