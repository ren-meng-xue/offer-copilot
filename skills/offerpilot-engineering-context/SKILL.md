---
name: offerpilot-engineering-context
description: Use this skill when working on OfferPilot technical architecture, frontend-backend1 separation, project structure, API planning, deployment structure, or implementation tradeoffs.
---

# OfferPilot Engineering Context

Use this skill when the task depends on OfferPilot's chosen engineering direction and repository conventions.

## Use This Skill For

- Defining project structure
- Choosing or justifying the technical stack
- Planning frontend and backend responsibilities
- Planning deployment structure
- Translating product modules into engineering modules

## Workflow

1. Read [references/stack-recommendation.md](references/stack-recommendation.md) for the current baseline stack.
2. Read [references/project-structure.md](references/project-structure.md) for top-level repository conventions.
3. Read [references/deployment-boundary.md](references/deployment-boundary.md) when the task involves `deploy/`, environments, or release planning.

## Working Rules

- Assume frontend-backend separation.
- Default frontend direction: `Next.js + TypeScript`.
- Default backend direction: `FastAPI + Python`.
- Keep recommendations MVP-first and avoid premature microservice design.
- Treat `deploy/` as a deployment/configuration area, not a business-code directory.

