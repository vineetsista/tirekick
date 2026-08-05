"use client";

import { useActionState } from "react";
import { startAnalysis, type UploadState } from "./actions";

/**
 * The upload form. Plain fields, one file input, no wizard: the person filling
 * this in is looking at a listing with photographs already on their phone, and
 * every field except the media itself is optional because the pipeline treats
 * absence honestly - a missing VIN means no records check, and the report says
 * so rather than working around it.
 */

const initialState: UploadState = { error: null };

export function UploadForm() {
  const [state, formAction, isPending] = useActionState(startAnalysis, initialState);

  return (
    <form action={formAction} style={{ display: "grid", gap: 24 }}>
      <section>
        <div className="mono-label" style={{ marginBottom: 8 }}>
          Media
        </div>
        <div className="panel" style={{ display: "grid", gap: 10 }}>
          <input
            type="file"
            name="media"
            multiple
            required
            accept=".jpg,.jpeg,.png,.webp,.heic,.heif,.mp4,.mov,.webm,.m4v,.wav,.mp3,.m4a,.aac,.flac,.ogg,.txt,.pdf"
            style={{ fontSize: 14 }}
          />
          <div className="prose muted" style={{ fontSize: 12 }}>
            Photographs of the exterior, interior, engine bay and tires; a slow
            walkaround video; an idle recording; any paperwork the seller shared.
            More angles mean fewer sections marked &ldquo;could not assess&rdquo;.
          </div>
        </div>
      </section>

      <section style={{ display: "grid", gap: 12 }}>
        <div className="mono-label">About the listing (all optional)</div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
            gap: 12,
          }}
        >
          <Field label="VIN" name="vin" placeholder="17 characters" />
          <Field label="Asking price, USD" name="askingPriceUsd" type="number" placeholder="8900" />
          <Field label="Seller-stated mileage" name="sellerStatedMileage" type="number" placeholder="128540" />
          <Field label="Year" name="listingYear" type="number" placeholder="2013" />
          <Field label="Make" name="listingMake" placeholder="Honda" />
          <Field label="Model" name="listingModel" placeholder="Accord" />
        </div>
        <label style={{ display: "grid", gap: 6 }}>
          <span className="mono-label">Anything you noticed yourself</span>
          <textarea
            name="buyerNotes"
            rows={3}
            placeholder="Seller says the transmission was replaced in 2021. Rattle at cold start."
            style={inputStyle}
          />
        </label>
      </section>

      {state.error && (
        <div
          className="panel prose"
          role="alert"
          style={{ borderLeft: "3px solid var(--tk-sev-major)", fontSize: 14 }}
        >
          <div className="mono-label" style={{ marginBottom: 8 }}>
            That did not work
          </div>
          {state.error}
        </div>
      )}

      <div>
        {/* One button, and while the pipeline runs it says so rather than
            going dead. Analysis is seconds locally, not instant. */}
        <button type="submit" className="btn btn-primary" disabled={isPending}>
          {isPending ? "Analyzing the media you provided…" : "Run the analysis"}
        </button>
      </div>
    </form>
  );
}

const inputStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--tk-line)",
  color: "inherit",
  font: "inherit",
  fontSize: 14,
  padding: "10px 12px",
  borderRadius: 2,
};

function Field({
  label,
  name,
  type = "text",
  placeholder,
}: {
  label: string;
  name: string;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label style={{ display: "grid", gap: 6 }}>
      <span className="mono-label">{label}</span>
      <input type={type} name={name} placeholder={placeholder} style={inputStyle} />
    </label>
  );
}
