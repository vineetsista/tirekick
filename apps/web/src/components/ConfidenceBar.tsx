/**
 * A ten-segment discrete bar. Discrete on purpose (BRAND.md): segments read as a
 * measurement, a smooth gradient reads as decoration. The number is always
 * adjacent - a bar on its own is not a confidence, it is a mood.
 */
export function ConfidenceBar({
  value,
  color,
  label = "CONF",
}: {
  value: number;
  color: string;
  label?: string;
}) {
  const filled = Math.round(value * 10);
  return (
    <span
      style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
      title={`${label} ${value.toFixed(2)}`}
    >
      <span className="mono-label" style={{ letterSpacing: "0.12em" }}>
        {label}
      </span>
      <span style={{ display: "inline-flex", gap: 2 }} aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            style={{
              width: 7,
              height: 12,
              background: i < filled ? color : "var(--tk-line)",
            }}
          />
        ))}
      </span>
      <span style={{ fontSize: 13, color }}>{value.toFixed(2)}</span>
    </span>
  );
}
