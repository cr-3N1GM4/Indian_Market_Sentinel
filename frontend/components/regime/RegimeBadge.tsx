"use client";

import { REGIME_COLORS, REGIME_LABELS } from "@/lib/types";

interface RegimeBadgeProps {
  regime: string;
  confidence?: number | null;
  size?: "sm" | "md" | "lg";
}

export default function RegimeBadge({
  regime,
  confidence,
  size = "md",
}: RegimeBadgeProps) {
  const color = REGIME_COLORS[regime] || "#64748B";
  const label = REGIME_LABELS[regime] || regime;
  const isCrisis = regime === "crisis_liquidity";

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-3 py-1 text-sm",
    lg: "px-4 py-2 text-base font-semibold",
  };

  return (
    <div
      className={`inline-flex items-center gap-2 rounded font-mono ${sizeClasses[size]} ${
        isCrisis ? "animate-pulse" : ""
      }`}
      style={{
        backgroundColor: `${color}15`,
        border: `1px solid ${color}50`,
        color: color,
      }}
    >
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span>{label}</span>
      {confidence != null && (
        <span className="text-ims-text-secondary text-xs">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}
