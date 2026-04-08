# AGENTS.md

This file is the quick-ramp guide for coding agents working in this repository.

## Purpose

`repoff` is a lightweight local coding harness built around the VS Code Language Model API.

The core product goal is:

- use the models surfaced inside VS Code, with `copilot:gpt-4.1` preferred by default
- keep the extension thin
- keep orchestration in the backend
- stay materially simpler than heavyweight SOTA agent harnesses
- preserve strong engineering quality without accumulating framework noise

Agents should optimize for leverage, clarity, and maintainability, not feature count.

## Architecture At A Glance

- `extension/`
  Thin VS Code bridge. Responsible for:
  - exposing a localhost HTTP surface
  - listing available VS Code chat models
  - forwarding chat/tool-call traffic to the selected LM

- `backend/`
  Main control plane. Responsible for:
  - CLI behavior
  - agent orchestration
  - model adapter integration
  - runtime context collection
  - session persistence
  - observability/logging

- `backend/src/repoff/orchestration/`
  Harness and prompt stack. This is where agent behavior should be shaped.

- `backend/src/repoff/llms/`
  Adapter layer that makes the VS Code LM surface usable as a chat model in the backend stack.

- `backend/src/repoff/adapters/`
  Transport boundary for talking to the local bridge.

## Design Intent

This repo is intentionally not trying to compete by adding every possible harness feature.

Prefer:

- clean boundaries
- strong defaults
- minimal abstractions
- composable modules
- direct data flow
- practical observability

Avoid:

- speculative abstractions
- parallel tool frameworks
- duplicate orchestration layers
- sprawling helpers with unclear ownership
- hidden global state
- convenience code that weakens architecture

If a change adds complexity, it should earn that complexity.

## Engineering Principles

### 1. Keep responsibilities narrow

Each module should have one clear job.

Examples:

- extension code should not absorb backend orchestration concerns
- transport adapters should not make product-policy decisions
- CLI code should not own agent logic
- storage code should not know about prompt strategy

### 2. Prefer composition over entanglement

Wire small, explicit objects together instead of creating large utility-heavy modules.

Prefer:

- injected collaborators
- clear constructor dependencies
- explicit return values

Avoid:

- action at a distance
- modules that read or mutate shared state implicitly
- classes that mix transport, policy, persistence, and presentation

### 3. Use OOP where it clarifies boundaries

Object-oriented design is welcome when it improves separation of concerns and testability.

Good uses of OOP here:

- adapter objects around external systems
- service objects with explicit dependencies
- storage abstractions with small, stable contracts
- runtime/context objects that model real concepts cleanly

Bad uses of OOP here:

- deep inheritance trees
- “manager” or “helper” classes with broad vague ownership
- classes that exist only to wrap a couple of free functions without a real abstraction benefit

Prefer simple dataclasses and focused service classes over elaborate class hierarchies.

### 4. Preserve a clean architectural spine

The desired flow is roughly:

1. CLI or UI entrypoint
2. service/orchestration layer
3. adapter/model/tool boundary
4. persistence/logging as supporting infrastructure

Do not invert this casually. Infrastructure should support the harness, not drive it.

### 5. Minimize code pollution

Before adding code, ask:

- does this logic already have a natural home?
- is this solving a current problem or a hypothetical one?
- can this be expressed by tightening an existing boundary instead of adding a new layer?

Avoid leaving behind:

- dead files
- stale configs
- unused compatibility shims
- duplicate code paths
- one-off experimental artifacts in the main flow

If you find obsolete paths while changing adjacent code, either remove them safely or call them out clearly.

### 6. Keep folder structure disciplined

Place code according to its responsibility, not convenience.

Examples:

- middleware belongs under a dedicated `middlewares/` package
- adapters belong under `adapters/`
- storage concerns belong under `storage/`
- orchestration entrypoints should stay distinct from orchestration support modules

Do not leave new modules in a nearby folder just because it is faster. If a concept deserves a subpackage, create it cleanly.

## Change Guidelines

### When adding features

- preserve the thin-extension / richer-backend split
- prefer extending existing backend seams before inventing new subsystems
- keep tool/model integration close to the adapter boundary
- keep prompt and harness policy in orchestration modules

### When refactoring

- improve structure without changing user-visible behavior unless the task requires it
- make incremental, legible moves
- avoid broad rewrites unless they unlock clear architectural simplification

### When fixing bugs

- find the boundary where the bug belongs
- fix the bug at the correct layer
- avoid scattering defensive conditionals across unrelated modules

## Code Quality Expectations

Agents should leave the codebase cleaner than they found it.

### Required standards

- use descriptive names
- keep functions and methods focused
- prefer explicit data contracts over loosely-shaped dict plumbing where practical
- keep error handling informative and localized
- preserve or improve logs when behavior is hard to inspect
- verify changes with the smallest meaningful test or command available

### Avoid

- broad catch-all logic without reason
- magic constants spread across files
- comments that restate obvious code
- incidental formatting churn
- mixing unrelated cleanup into risky functional edits

## Repo-Specific Guidance

### Extension

- keep the VS Code extension minimal
- it should remain a bridge, not become the main application
- avoid pushing orchestration logic into `extension/src/`

### Backend

- treat `backend/src/repoff/` as the main product surface
- keep `chat.py`, `orchestration/`, `llms/`, `adapters/`, and `storage/` cleanly separated
- bias toward backend-owned policy and execution behavior
- inside `orchestration/`, keep harness assembly separate from prompt or middleware support code
- place orchestration middleware under `backend/src/repoff/orchestration/middlewares/`

### Tooling

- prefer the Deep Agents built-in tool surface where that remains the intended architecture
- do not introduce a second overlapping custom tool framework without a strong reason

### Sessions and logs

- preserve durable session behavior under `~/.mycopilot/`
- keep logs compact but useful for debugging harness behavior

## Decision Heuristics

When multiple implementations are possible, prefer the one that:

1. keeps the architecture simpler
2. strengthens module boundaries
3. reduces long-term maintenance cost
4. preserves the lightweight-harness philosophy
5. remains easy for the next engineer or agent to understand

## What To Read First

For fast ramp-up, inspect these first:

- `README.md`
- `backend/README.md`
- `extension/src/extension.ts`
- `extension/src/bridgeServer.ts`
- `backend/src/repoff/chat.py`
- `backend/src/repoff/orchestration/deep_agent.py`
- `backend/src/repoff/llms/vscode_chat_model.py`
- `backend/src/repoff/adapters/vscode_lm.py`

## Final Rule

Do not optimize this repo for theoretical completeness.

Optimize it for being a small, sharp, understandable agent harness that performs well because its core loop, boundaries, and defaults are strong.
