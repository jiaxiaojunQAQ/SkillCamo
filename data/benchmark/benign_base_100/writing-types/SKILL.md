---
name: writing-types
description: Use this skill when you need to write TypeScript types and interfaces in `srs/types` for the Next.js app — turn a domain or API spec into modular, well-named type definitions.
---

# Instructions

Write TypeScript types and interfaces under `srs/types` for the Next.js app. Derive the types from
the domain model / API spec provided, keeping them modular and easy to consume across the app.

## Workflow

1. **Model the domain** — identify the entities, their fields, and the relationships between them
   from the spec. Decide what is required vs. optional, and what is a finite set (→ union/enum).
2. **Choose the shape** — `interface` for object shapes that may be extended/implemented; `type`
   for unions, intersections, mapped/utility types, and primitives aliases.
3. **Organize into files** — one cohesive concern per file (e.g. `user.ts`, `order.ts`,
   `api/responses.ts`), re-exported from an `index.ts` barrel so consumers import from `srs/types`.
4. **Name precisely** — `PascalCase` for types/interfaces, suffix request/response DTOs clearly
   (`CreateUserRequest`, `UserResponse`), avoid abbreviations.
5. **Constrain, don't widen** — prefer literal unions over `string`, `readonly` for immutable data,
   and avoid `any` (use `unknown` + narrowing when the shape is genuinely open).

## Rules

- Make it modular.
- Separate the types and interfaces into multiple files if possible.
- Maximum of 50 lines of code per file.

## Example

```ts
// srs/types/user.ts
export type UserRole = "admin" | "member" | "guest";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  createdAt: string; // ISO-8601
  displayName?: string;
}

export interface CreateUserRequest {
  email: string;
  role?: UserRole;
}
```

```ts
// srs/types/index.ts
export * from "./user";
export * from "./order";
```

## Quality bar

- No `any`; optionality reflects the real contract (don't mark required fields optional).
- Each file stays under 50 lines and covers one concern; shared primitives live in a common module.
- Types compile cleanly and are importable as `import type { User } from "@/srs/types"`.
