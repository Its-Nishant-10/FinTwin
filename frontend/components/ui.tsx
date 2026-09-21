/**
 * Small presentational pieces shared across the dashboard.
 *
 * Status is never colour alone: every tone that means good/caution/critical is
 * drawn with an icon and a text label as well.
 */

import type { ReactNode } from "react";

export type Tone = "good" | "caution" | "critical" | "info" | "neutral";

type IconName = "check" | "alert" | "cross" | "info" | "up" | "down";

const PATHS: Record<IconName, ReactNode> = {
  check: <path d="M3.5 8.5l3 3 6-7" />,
  alert: (
    <>
      <path d="M8 2.2l6.3 11H1.7z" />
      <path d="M8 6.5v3.2M8 11.6v.1" />
    </>
  ),
  cross: <path d="M4 4l8 8M12 4l-8 8" />,
  info: (
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7.3v3.6M8 5v.1" />
    </>
  ),
  up: <path d="M8 12.5v-9M4 7l4-4 4 4" />,
  down: <path d="M8 3.5v9M4 9l4 4 4-4" />,
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 16 16"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

const TONE_ICON: Record<Tone, IconName | null> = {
  good: "check",
  caution: "alert",
  critical: "cross",
  info: "info",
  neutral: null,
};

export function StatusBadge({ tone, children }: { tone: Tone; children: ReactNode }) {
  const icon = TONE_ICON[tone];
  return (
    <span className="badge" data-tone={tone}>
      {icon && <Icon name={icon} />}
      {children}
    </span>
  );
}

export function StatTile({
  label,
  value,
  sub,
  hero = false,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  hero?: boolean;
}) {
  return (
    <div className={hero ? "tile tile--hero" : "tile"}>
      <div className="stat-label">{label}</div>
      <div className="tile__value">{value}</div>
      {sub && <div className="tile__sub">{sub}</div>}
    </div>
  );
}

/** A 0-100 track. `marker` draws a limit tick, e.g. the user's own concentration cap. */
export function Meter({
  value,
  tone,
  label,
  marker,
}: {
  value: number;
  tone: Tone;
  label: string;
  marker?: number | null;
}) {
  const clamp = (n: number) => Math.min(100, Math.max(0, n));
  return (
    <div
      className="meter"
      data-tone={tone}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamp(value))}
    >
      <div className="meter__fill" style={{ width: `${clamp(value)}%` }} />
      {marker != null && (
        <div className="meter__marker" style={{ left: `${clamp(marker)}%` }} aria-hidden="true" />
      )}
    </div>
  );
}

export function Notice({
  tone = "info",
  children,
  action,
}: {
  tone?: Tone;
  children: ReactNode;
  action?: ReactNode;
}) {
  const icon = TONE_ICON[tone];
  return (
    <div className="notice" data-tone={tone} role={tone === "critical" ? "alert" : "note"}>
      {icon && <Icon name={icon} />}
      <div className="notice__body">{children}</div>
      {action}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="spinner" role="status">
      <span className="spinner__dot" aria-hidden="true" />
      {label}
    </span>
  );
}
