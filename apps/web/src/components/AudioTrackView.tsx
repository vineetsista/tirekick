import type { AudioTrack } from "@tirekick/shared";
import { assetUrl } from "@/lib/report";

/**
 * The audio section: a picture, the numbers under it, and a plain statement that
 * no claims are attached to either.
 *
 * This is what LAW 4 looks like when it costs something. There is a working
 * transient detector behind this component and it found three sharp onsets in the
 * fixture clip. It would be trivial - and it would look impressive - to label
 * those "possible valvetrain tick". We have not measured whether that label would
 * be right, so the report shows where to listen and says nothing about what it
 * heard.
 */
export function AudioTrackView({
  track,
  inspectionId,
}: {
  track: AudioTrack;
  inspectionId: string;
}) {
  const spectrogram = track.spectrogramPath
    ? assetUrl(inspectionId, track.spectrogramPath)
    : null;

  return (
    <div className="panel">
      {/* The gate, stated before the picture rather than under it. */}
      <div
        className="prose"
        style={{
          border: "1px solid var(--tk-locked)",
          borderLeftWidth: 4,
          background: "rgba(163,113,247,0.07)",
          padding: "14px 16px",
          fontSize: 13,
          lineHeight: 1.6,
          marginBottom: 20,
        }}
      >
        {track.claimsStatement}
      </div>

      {spectrogram && (
        <figure style={{ margin: 0 }}>
          <div
            style={{
              position: "relative",
              border: "1px solid var(--tk-line)",
              lineHeight: 0,
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={spectrogram}
              alt={`Spectrogram of ${track.assetId}`}
              style={{ width: "100%", height: "auto", display: "block" }}
            />

            {/* Transient markers, positioned by time. Deliberately unlabelled:
                a caption naming what made the sound is the claim we have not
                earned. */}
            {track.transients.map((t, i) => {
              const left = `${Math.min(100, (t.atSec / Math.max(track.durationSec, 0.001)) * 100)}%`;
              return (
                <div key={i}>
                  <div
                    style={{
                      position: "absolute",
                      left,
                      top: 0,
                      bottom: 0,
                      width: 1,
                      background: "var(--tk-sev-major)",
                      opacity: 0.85,
                    }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      left,
                      top: 4,
                      transform: "translateX(-50%)",
                      fontSize: 9,
                      letterSpacing: "0.1em",
                      color: "var(--tk-sev-major)",
                      background: "rgba(10,12,14,0.75)",
                      padding: "1px 4px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {t.atSec.toFixed(1)}s
                  </div>
                </div>
              );
            })}
          </div>

          <figcaption
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: 6,
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--tk-unknown)",
            }}
          >
            <span>0s</span>
            <span>frequency, low at bottom / log scale</span>
            <span>{track.durationSec.toFixed(0)}s</span>
          </figcaption>
        </figure>
      )}

      {/* Let them hear it. The clip is the evidence; the picture is a view of it. */}
      <audio
        controls
        preload="none"
        src={assetUrl(inspectionId, `${track.assetId}.wav`)}
        // colorScheme tells the browser to draw its native control dark.
        // The alternative is rebuilding a media player, which is a lot of
        // surface area for something the platform already does well.
        style={{ width: "100%", marginTop: 16, colorScheme: "dark" }}
      >
        Your browser cannot play this audio clip.
      </audio>

      <div className="prose" style={{ fontSize: 13, marginTop: 18 }}>
        {track.transientStatement}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 16,
          marginTop: 20,
          paddingTop: 16,
          borderTop: "1px solid var(--tk-line)",
        }}
      >
        <Measure label="Length" value={`${track.durationSec.toFixed(1)}s`} />
        <Measure
          label="Dominant tone"
          value={track.dominantHz === null ? "-" : `${track.dominantHz.toFixed(1)} Hz`}
        />
        <Measure
          label="Implied idle"
          value={track.impliedRpm === null ? "-" : `${track.impliedRpm.toLocaleString()} rpm`}
        />
        <Measure label="Level" value={`${track.rmsDbfs.toFixed(0)} dBFS`} />
        <Measure
          label="Clipped"
          value={`${(track.clippedFraction * 100).toFixed(1)}%`}
        />
      </div>

      <div className="prose muted" style={{ fontSize: 12, marginTop: 14 }}>
        {track.impliedRpmBasis}
      </div>

      {!track.usable && (
        <div
          style={{
            marginTop: 18,
            paddingTop: 14,
            borderTop: "1px solid var(--tk-line)",
          }}
        >
          <div className="mono-label" style={{ color: "var(--tk-sev-major)" }}>
            This recording is not good enough to analyze
          </div>
          <ul className="prose" style={{ margin: "10px 0 0", paddingLeft: 20, fontSize: 13 }}>
            {track.qualityProblems.map((problem, i) => (
              <li key={i} style={{ marginBottom: 6 }}>
                {problem}
              </li>
            ))}
          </ul>
          <div className="prose muted" style={{ fontSize: 12, marginTop: 10 }}>
            {track.qualityStatement}
          </div>
        </div>
      )}
    </div>
  );
}

function Measure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mono-label">{label}</div>
      <div style={{ fontSize: 18 }}>{value}</div>
    </div>
  );
}
