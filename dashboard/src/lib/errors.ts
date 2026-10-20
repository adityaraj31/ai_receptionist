import type { components } from "./api-schema";

type ValidationError = components["schemas"]["ValidationError"];

export class ApiError extends Error {
  status: number;
  details: string[];

  constructor(message: string, status: number, details: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function isValidationError(value: unknown): value is ValidationError {
  return (
    typeof value === "object" &&
    value !== null &&
    "msg" in value &&
    typeof (value as { msg: unknown }).msg === "string"
  );
}

function formatValidationError(error: ValidationError): string {
  const field = error.loc
    .filter((part) => part !== "body" && part !== "query" && part !== "path")
    .map(String)
    .join(".");

  return field ? `${field}: ${error.msg}` : error.msg;
}

export function parseApiError(status: number, payload: unknown): ApiError {
  if (typeof payload === "string" && payload.trim()) {
    return new ApiError(payload, status);
  }

  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;

    if (typeof detail === "string") {
      return new ApiError(detail, status);
    }

    if (Array.isArray(detail)) {
      const details = detail
        .filter(isValidationError)
        .map(formatValidationError);
      if (details.length > 0) {
        return new ApiError(details[0], status, details);
      }
    }
  }

  if (status === 401) {
    return new ApiError("Your session has expired. Please sign in again.", status);
  }

  if (status === 403) {
    return new ApiError("You do not have permission to do that.", status);
  }

  if (status === 404) {
    return new ApiError("That item could not be found.", status);
  }

  return new ApiError(`Request failed with status ${status}.`, status);
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}
