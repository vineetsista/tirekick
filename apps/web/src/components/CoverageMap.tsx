import type { Report, Severity, ViewClass } from "@tirekick/shared";
import { severityColor } from "@/lib/report";

/**
 * ---------------------------------------------------------------------------
 * THE SIGNATURE VISUAL
 * ---------------------------------------------------------------------------
 *
 * Every other vehicle-inspection interface is a checklist of green ticks. This
 * product cannot produce one: LAW 2 forbids clearing brakes, restraints,
 * structure or steering at any confidence, and 0 of 16 finding types have a
 * measured accuracy. What TIREKICK actually knows is *where it looked*, and the
 * most useful thing it can hand a buyer is a map of where it did not.
 *
 * Three states for each region of the car, and the third is the point:
 *
 *   FLAGGED       a finding cites a photograph of this region. Severity colour.
 *   LOOKED AT     a photograph arrived and nothing adverse was visible in it.
 *                 Hairline, no fill, and deliberately NOT green - it is a
 *                 statement about the photograph, not a pass.
 *   NOT PROVIDED  no photograph of this ever reached us. Dashed, dim. Nothing in
 *                 the report describes what it would have shown.
 *
 * Over the top of those, the four locked systems, drawn where they physically
 * live rather than listed in a footnote: brakes behind the wheels, steering at
 * the dash, restraints in the cabin, structure as the outline of the car itself.
 * A buyer should be able to see that the shell of the vehicle is the exact thing
 * we will never tell them is sound.
 *
 * ---------------------------------------------------------------------------
 * A ZONE LIGHTS UP FROM THE PHOTOGRAPH A FINDING CITES, NOT FROM ITS SYSTEM
 * ---------------------------------------------------------------------------
 *
 * The first version of this component keyed each zone off the finding's `system`
 * field. One corrosion finding on the driver-side rocker panel therefore lit the
 * front, the rear, and both flanks, because all four are `system: "exterior"`.
 * It reported damage on parts of the car nothing had been found on - the precise
 * failure this component exists to prevent, committed by the component itself.
 *
 * So a zone flags only when a finding's `image_region` evidence cites an asset
 * whose `viewClass` is that zone. That is a fact about which pixels were looked
 * at, which is the only thing the map is entitled to assert.
 */

type ZoneState = "flagged" | "looked" | "missing";

interface Zone {
  view: ViewClass;
  label: string;
  /** x, y, w, h in the 260x360 viewBox. */
  rect: [number, number, number, number];
}

const ZONES: Zone[] = [
  { view: "exterior_front", label: "Front", rect: [72, 8, 116, 46] },
  { view: "engine_bay", label: "Engine bay", rect: [72, 58, 116, 48] },
  { view: "dash", label: "Dash", rect: [72, 110, 116, 30] },
  { view: "interior_front", label: "Interior front", rect: [72, 144, 116, 60] },
  { view: "interior_rear", label: "Interior rear", rect: [72, 208, 116, 54] },
  { view: "exterior_rear", label: "Rear", rect: [72, 266, 116, 46] },
  { view: "exterior_side_left", label: "Left", rect: [16, 118, 44, 120] },
  { view: "exterior_side_right", label: "Right", rect: [200, 118, 44, 120] },
];

/** All four wheels are one view class, so they share one state. */
const WHEELS: [number, number, number, number][] = [
  [16, 62, 44, 46],
  [200, 62, 44, 46],
  [16, 248, 44, 46],
  [200, 248, 44, 46],
];

/** Views that occupy a rectangle on the drawing above. */
export const PLACED_VIEWS: ReadonlySet<ViewClass> = new Set<ViewClass>([
  ...ZONES.map((z) => z.view),
  "tire",
]);

/**
 * A readable name for every view class in the contract.
 *
 * Exhaustive by type rather than by diligence: `Record<ViewClass, string>` will
 * not compile if a view class is added to the contract and not named here, which
 * is the only reason it is safe for the row below to be derived from data.
 */
const VIEW_LABEL: Record<ViewClass, string> = {
  exterior_front: "Front",
  exterior_rear: "Rear",
  exterior_side_left: "Left",
  exterior_side_right: "Right",
  exterior_three_quarter: "Three-quarter",
  interior_front: "Interior front",
  interior_rear: "Interior rear",
  engine_bay: "Engine bay",
  odometer: "Odometer",
  dash: "Dash",
  tire: "Tires",
  vin_plate: "VIN plate",
  document: "Document",
  undercarriage: "Undercarriage",
  unknown: "Unclassified",
};

/**
 * Where each locked system sits on the drawing.
 *
 * Not a state a zone can be in - a locked system is a refusal that sits on top of
 * whatever the photographs did or did not show. `structure` is the outline
 * itself, so it has no marker of its own.
 */
const LOCKED_PLACEMENT: Record<string, { label: string; at: [number, number][] }> = {
  // Corners, not centres: a marker over the middle of a zone sat on top of its
  // label and made both unreadable.
  brakes: {
    label: "Brakes",
    at: [
      [50, 70],
      [234, 70],
      [50, 256],
      [234, 256],
    ],
  },
  steering: { label: "Steering", at: [[180, 118]] },
  restraints: { label: "Restraints", at: [[180, 152]] },
};

const SEVERITY_RANK: Record<Severity, number> = {
  info: 0,
  minor: 1,
  major: 2,
  critical: 3,
};

export function CoverageMap({ report }: { report: Report }) {
  const received = new Set(report.coverage.receivedViews);

  /** assetId -> viewClass, so a finding's evidence can be traced to a region. */
  const viewOf = new Map<string, ViewClass | null>(
    report.assets.map((a) => [a.id, a.viewClass]),
  );

  /** The worst severity of any finding citing a photograph of this view. */
  const flagged = new Map<ViewClass, Severity>();
  const countFor = new Map<ViewClass, number>();
  for (const f of report.findings) {
    for (const ev of f.evidence) {
      if (ev.kind !== "image_region") continue;
      const view = viewOf.get(ev.assetId);
      if (!view) continue;
      const current = flagged.get(view);
      if (!current || SEVERITY_RANK[f.severity] > SEVERITY_RANK[current]) {
        flagged.set(view, f.severity);
      }
      countFor.set(view, (countFor.get(view) ?? 0) + 1);
    }
  }

  const lockedSystems = report.systems
    .filter((s) => s.status === "locked_mechanic_required")
    .map((s) => s.system);

  function stateFor(view: ViewClass): [ZoneState, Severity | null] {
    const severity = flagged.get(view);
    if (severity) return ["flagged", severity];
    return received.has(view) ? ["looked", null] : ["missing", null];
  }

  /**
   * The views that have no rectangle on the drawing, taken from the report
   * rather than from a list kept here.
   *
   * A hardcoded row was three view classes long while the contract had fifteen
   * and the pipeline requested twelve. It happened to agree with the pipeline on
   * the day it was written, which is the same arrangement - a second copy of a
   * list, kept in step by attention - that this project has now found in the
   * enums, the asset columns and the landing page. Here the cost is specific: a
   * view added to `REQUESTED_VIEWS` would go missing from the one component
   * whose entire purpose is showing what was not covered, and the legend would
   * quietly count it as neither photographed nor missing.
   *
   * Flagged views are unioned in as well, so a finding can never cite a
   * photograph that lights nothing anywhere on this map.
   */
  const unplaced: ViewClass[] = [
    ...new Set<ViewClass>([...report.coverage.requestedViews, ...flagged.keys()]),
  ].filter((v) => !PLACED_VIEWS.has(v));

  const allViews: ViewClass[] = [...PLACED_VIEWS, ...unplaced];
  const counts = { flagged: 0, looked: 0, missing: 0 };
  for (const v of allViews) counts[stateFor(v)[0]] += 1;

  const [tireState, tireSeverity] = stateFor("tire");
  const tire = paint(tireState, tireSeverity);

  return (
    <div
      style={{
        display: "grid",
        // The drawing is capped at 320px, so an equal-fraction split left it
        // marooned in the middle of a 600px column with the legend it labels
        // half a screen away. The map column is sized to the map; the legend
        // takes the rest. Both collapse to one column under ~620px.
        gridTemplateColumns: "repeat(auto-fit, minmax(min(320px, 100%), auto))",
        gap: "var(--s-6)",
        alignItems: "start",
      }}
    >
      <svg
        viewBox="0 0 260 360"
        role="img"
        aria-label={`Coverage map of the vehicle. ${counts.flagged} regions flagged, ${counts.looked} photographed with nothing flagged, ${counts.missing} never photographed. ${lockedSystems.length} systems locked and never assessed remotely: ${lockedSystems.join(", ")}.`}
        style={{ width: "100%", height: "auto", display: "block", maxWidth: 320 }}
      >
        <defs>
          <pattern
            id="tk-locked-hatch"
            width="6"
            height="6"
            patternTransform="rotate(45)"
            patternUnits="userSpaceOnUse"
          >
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--tk-locked)" strokeWidth="1.2" />
          </pattern>
        </defs>

        {/* Structure is locked, and the outline of the car IS the structure. */}
        <rect
          x="8"
          y="4"
          width="244"
          height="352"
          fill="none"
          stroke="var(--tk-locked)"
          strokeWidth="1.5"
          strokeDasharray="3 5"
        />
        <text
          x="130"
          y="352"
          textAnchor="middle"
          style={{
            fontFamily: "var(--tk-display)",
            fontSize: 7.5,
            letterSpacing: "0.14em",
            fill: "var(--tk-locked)",
          }}
        >
          STRUCTURE / LOCKED
        </text>

        {WHEELS.map((r, i) => (
          <rect
            key={i}
            x={r[0]}
            y={r[1]}
            width={r[2]}
            height={r[3]}
            fill={tire.fill}
            stroke={tire.stroke}
            strokeWidth="1.25"
            strokeDasharray={tire.dash}
          />
        ))}

        {ZONES.map((z) => {
          const [state, severity] = stateFor(z.view);
          const p = paint(state, severity);
          const [x, y, w, h] = z.rect;
          const n = countFor.get(z.view) ?? 0;
          return (
            <g key={z.view}>
              <rect
                x={x}
                y={y}
                width={w}
                height={h}
                fill={p.fill}
                stroke={p.stroke}
                strokeWidth="1.25"
                strokeDasharray={p.dash}
              />
              <text
                x={x + w / 2}
                y={y + h / 2 + (n > 0 ? -1 : 3)}
                textAnchor="middle"
                style={{
                  fontFamily: "var(--tk-display)",
                  fontSize: 8,
                  letterSpacing: "0.1em",
                  fill: p.stroke,
                }}
              >
                {z.label.toUpperCase()}
              </text>
              {n > 0 && (
                <text
                  x={x + w / 2}
                  y={y + h / 2 + 11}
                  textAnchor="middle"
                  style={{
                    fontFamily: "var(--tk-mono)",
                    fontSize: 8,
                    fill: p.stroke,
                  }}
                >
                  {n} finding{n > 1 ? "s" : ""}
                </text>
              )}
            </g>
          );
        })}

        {/* The locked systems, where they physically are. */}
        {lockedSystems.flatMap((system) => {
          const placement = LOCKED_PLACEMENT[system];
          if (!placement) return [];
          return placement.at.map(([cx, cy], i) => (
            <g key={`${system}-${i}`}>
              <rect
                x={cx - 6}
                y={cy - 6}
                width={12}
                height={12}
                fill="url(#tk-locked-hatch)"
                stroke="var(--tk-locked)"
                strokeWidth="1"
              />
              <title>{`${placement.label}: not remotely verifiable, independent mechanic required`}</title>
            </g>
          ));
        })}
      </svg>

      <div>
        <div style={{ display: "grid", gap: "var(--s-4)" }}>
          <Legend
            swatch={
              <Swatch
                stroke="var(--tk-sev-major)"
                fill="color-mix(in srgb, var(--tk-sev-major) 18%, transparent)"
              />
            }
            n={counts.flagged}
            title="Flagged"
            body="A finding cites a photograph of this region. Every one is listed below with the picture it came from."
          />
          <Legend
            swatch={<Swatch stroke="var(--tk-paper)" />}
            n={counts.looked}
            title="Photographed, nothing flagged"
            body="An image arrived and a pass ran over it. Nothing adverse was visible. That is a statement about the photograph and not a pass."
          />
          <Legend
            swatch={<Swatch stroke="var(--tk-unknown)" dashed />}
            n={counts.missing}
            title="Never photographed"
            body="No image of this reached us. Nothing in this report describes what it would have shown."
          />
          <Legend
            swatch={<Swatch stroke="var(--tk-locked)" hatched />}
            n={lockedSystems.length}
            title="Locked"
            body="Never assessed remotely, on any vehicle, at any confidence. An independent mechanic is the only route to an answer."
            names={lockedSystems}
          />
        </div>

        <div style={{ marginTop: "var(--s-5)" }}>
          <div className="label">Views with no place on a plan view</div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--s-2)",
              marginTop: "var(--s-2)",
            }}
          >
            {unplaced.map((view) => {
              const [state, severity] = stateFor(view);
              const p = paint(state, severity);
              return (
                <span
                  key={view}
                  className="chip"
                  style={{
                    color: p.stroke,
                    borderStyle: state === "missing" ? "dashed" : "solid",
                  }}
                >
                  {VIEW_LABEL[view]}
                </span>
              );
            })}
          </div>
        </div>

        <p className="prose-sm muted" style={{ marginTop: "var(--s-4)", marginBottom: 0 }}>
          {report.coverage.statement}
        </p>
      </div>
    </div>
  );
}

function paint(
  state: ZoneState,
  severity: Severity | null,
): { stroke: string; fill: string; dash?: string } {
  switch (state) {
    case "flagged": {
      const c = severityColor(severity ?? "minor");
      return { stroke: c, fill: `color-mix(in srgb, ${c} 18%, transparent)` };
    }
    case "looked":
      return { stroke: "var(--tk-paper)", fill: "transparent" };
    case "missing":
      return { stroke: "var(--tk-unknown)", fill: "transparent", dash: "3 4" };
  }
}

function Swatch({
  stroke,
  fill,
  dashed,
  hatched,
}: {
  stroke: string;
  fill?: string;
  dashed?: boolean;
  hatched?: boolean;
}) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width: 24,
        height: 15,
        border: `1.5px ${dashed ? "dashed" : "solid"} ${stroke}`,
        background: hatched
          ? `repeating-linear-gradient(45deg, ${stroke} 0 1.2px, transparent 1.2px 5px)`
          : (fill ?? "transparent"),
        flex: "0 0 auto",
      }}
    />
  );
}

function Legend({
  swatch,
  n,
  title,
  body,
  names,
}: {
  swatch: React.ReactNode;
  n: number;
  title: string;
  body: string;
  names?: string[];
}) {
  return (
    <div style={{ display: "flex", gap: "var(--s-3)", alignItems: "flex-start" }}>
      <span style={{ marginTop: 4 }}>{swatch}</span>
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--s-2)" }}>
          <span className="data" style={{ fontSize: "var(--t-md)" }}>
            {n}
          </span>
          <span className="label" style={{ color: "var(--tk-paper)" }}>
            {title}
          </span>
        </div>
        <p className="prose-sm dim" style={{ margin: "2px 0 0", fontSize: "var(--t-sm)" }}>
          {body}
          {names && names.length > 0 && (
            <>
              {" "}
              <span style={{ color: "var(--tk-locked)" }}>{names.join(", ")}.</span>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
