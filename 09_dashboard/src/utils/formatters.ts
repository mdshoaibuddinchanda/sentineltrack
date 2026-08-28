export function formatDistance(meters?: number | null): string {
  if (meters === undefined || meters === null || isNaN(meters)) return "--";
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

export function formatSpeed(kmh?: number | null): string {
  if (kmh === undefined || kmh === null || isNaN(kmh)) return "--";
  return `${Math.round(kmh)} km/h`;
}

export function formatScore(score?: number | null): string {
  if (score === undefined || score === null || isNaN(score)) return "--";
  return score.toFixed(2);
}

export function formatDuration(seconds?: number | null): string {
  if (seconds === undefined || seconds === null || isNaN(seconds)) return "--";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const remSec = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${remSec}s`;
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `${hrs}h ${remMins}m`;
}

export function formatDateTime(isoString?: string | null, includeSeconds = true): string {
  if (!isoString) return "--";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "--";
    return d.toLocaleString("en-IN", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: includeSeconds ? "2-digit" : undefined,
      hour12: false,
      timeZoneName: "short",
    });
  } catch {
    return "--";
  }
}

export function formatUtcTime(isoString?: string | null): string {
  if (!isoString) return "--";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "--";
    return d.toISOString().replace("T", " ").replace("Z", " UTC");
  } catch {
    return "--";
  }
}

export function formatRelativeTime(isoString?: string | null): string {
  if (!isoString) return "--";
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    if (isNaN(diffMs)) return "--";
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 5) return "just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    return `${diffDays}d ago`;
  } catch {
    return "--";
  }
}

export function maskRegistration(reg: string, enabled = false): string {
  if (!enabled || !reg || reg.length < 5) return reg;
  const start = reg.slice(0, 4);
  const end = reg.slice(-2);
  const maskLen = Math.max(2, reg.length - 6);
  return `${start}${"*".repeat(maskLen)}${end}`;
}
