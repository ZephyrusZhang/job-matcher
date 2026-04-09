/**
 * Read-only demo mode helpers.
 *
 * When `NEXT_PUBLIC_READ_ONLY_MODE` is set to a truthy value at build/runtime,
 * the cloud demo hides the three interactive features (smart recommendation,
 * job comparison, and settings) behind a full-page overlay. The backend
 * enforces the same restriction via `ReadOnlyMiddleware`.
 *
 * Use `NEXT_PUBLIC_*` so the value is inlined into the client bundle.
 */

const TRUTHY = new Set(["1", "true", "yes", "on"])

export const IS_READ_ONLY_MODE: boolean = TRUTHY.has(
  (process.env.NEXT_PUBLIC_READ_ONLY_MODE ?? "").trim().toLowerCase(),
)
