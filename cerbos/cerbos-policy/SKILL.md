---
name: cerbos-policy
description: Generate Cerbos authorization policies from requirements, PDFs, or specifications. Use when creating access control policies, resource permissions, derived roles, or RBAC/ABAC rules. Triggers on "cerbos", "authorization policy", "access control", "RBAC", "ABAC".
license: Apache-2.0
compatibility: Requires Docker for policy validation
metadata:
  author: cerbos
  version: "1.0"
allowed-tools: Read Write Edit Bash Glob Grep Task WebFetch
---

# Cerbos Policy Generator

Generate production-ready Cerbos authorization policies from natural language requirements or specification documents.

## Prerequisites

Before starting, verify Docker is available:

```bash
docker --version
```

If Docker is not installed, inform the user and provide installation guidance:

- **macOS/Windows**: Download [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux**: Install via package manager or see [docs.docker.com/engine/install](https://docs.docker.com/engine/install/)

**Do not proceed with policy generation until Docker is available.**

## Capabilities

1. **Generate policies** from requirements, PDFs, or bullet points
2. **Answer questions** about existing policies and Cerbos concepts
3. **Modify policies** based on requests, ensuring tests pass
4. **Explain policies** in plain language

## Quick Start

Describe your authorization requirements:
- What resources need protection?
- Who should access them (roles/principals)?
- What actions are allowed?
- What conditions apply?

## Output

Complete policy bundle:
- `_schemas/` - Attribute schemas
- `derived_roles/` - Shared role definitions
- `resource_policies/` - Policies with tests
- `role_policies/` - Role Policies (if using role-centric ABAC)

## Reference

- [references/REFERENCE.md](references/REFERENCE.md) — Policy syntax, CEL patterns, test structure, workflow

## Validation

All policies are validated using the Cerbos Docker container:
```bash
docker run --rm -v $(pwd):/policies ghcr.io/cerbos/cerbos:latest compile /policies
```
