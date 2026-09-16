/** The one typed API client. Screens never call fetch directly.
 *
 *  Types come from the backend's OpenAPI schema (`npm run gen:api`), so a Pydantic
 *  change shows up here as a compile error rather than a runtime surprise. */

import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./api-types.generated";

export type Schemas = components["schemas"];
export type ApiPaths = paths;

const baseUrl = import.meta.env["VITE_API_BASE_URL"];
if (typeof baseUrl !== "string" || baseUrl.length === 0) {
  throw new Error("VITE_API_BASE_URL is not set. Copy .env.example to .env at the repo root.");
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function isErrorBody(value: unknown): value is Schemas["ErrorResponse"] {
  return typeof value === "object" && value !== null && "error" in value;
}

/** Turn every non-2xx response into a thrown ApiError with the server's error shape. */
const raiseOnError: Middleware = {
  async onResponse({ response }) {
    if (response.ok) return response;
    let body: unknown = null;
    try {
      body = await response.clone().json();
    } catch {
      body = null;
    }
    if (isErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message, body.error.details ?? null);
    }
    throw new ApiError(response.status, "http_error", `${response.status} ${response.statusText}`, null);
  },
};

export const api = createClient<paths>({ baseUrl, credentials: "include" });
api.use(raiseOnError);

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
