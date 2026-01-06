// Global circuit breaker for notification API calls
// If we get a 403, stop all future notification fetches (until page reload)
let notificationsForbidden = false;

/**
 * Fetch project notification settings with circuit breaker protection.
 * Returns null if forbidden (403) or if circuit breaker is already tripped.
 */
export async function fetchProjectNotifications(
  projectId: string | number,
  headers: HeadersInit = {}
): Promise<{
  zapier_enabled: boolean;
  reminder_offsets_days: number[];
} | null> {
  // Hard stop: Circuit breaker already tripped
  if (notificationsForbidden) {
    return null;
  }

  try {
    const res = await fetch(`/api/projects/${projectId}/notifications`, {
      method: "GET",
      headers,
      credentials: "include",
    });

    // If 403, trip circuit breaker forever (until page reload)
    if (res.status === 403) {
      notificationsForbidden = true;
      return null;
    }

    if (!res.ok) {
      // Don't trip circuit breaker for other errors (500, 404, etc.)
      return null;
    }

    return await res.json();
  } catch (error) {
    // Network errors don't trip circuit breaker
    return null;
  }
}

/**
 * Update project notification settings with circuit breaker protection.
 * Returns null if forbidden (403) or if circuit breaker is already tripped.
 */
export async function updateProjectNotifications(
  projectId: string | number,
  data: {
    reminder_offsets_days: number[];
    zapier_enabled: boolean;
  },
  headers: HeadersInit = {}
): Promise<boolean> {
  // Hard stop: Circuit breaker already tripped
  if (notificationsForbidden) {
    return false;
  }

  try {
    const res = await fetch(`/api/projects/${projectId}/notifications`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      credentials: "include",
      body: JSON.stringify(data),
    });

    // If 403, trip circuit breaker forever (until page reload)
    if (res.status === 403) {
      notificationsForbidden = true;
      return false;
    }

    return res.ok;
  } catch (error) {
    // Network errors don't trip circuit breaker
    return false;
  }
}

/**
 * Reset circuit breaker (useful for testing or if plan changes)
 * Note: This should rarely be called in production
 */
export function resetNotificationCircuitBreaker(): void {
  notificationsForbidden = false;
}

