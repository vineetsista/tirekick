"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  GRANT_COOKIE_MAX_AGE_SECONDS,
  grantCookieName,
  issueGrant,
} from "@/lib/access";
import { analyse, createInspection } from "@/lib/inspections";

/**
 * Upload -> analyse -> owner grant -> the free result.
 *
 * This is the flow LAW 7's end-to-end test has driven through library calls
 * since P7, given a form. The moment the inspection exists its uploader gets
 * an `owner` grant in an httpOnly cookie: their teaser is theirs to read and
 * nobody else's, because an upload is somebody's prospective car, not content.
 *
 * Analysis here is the same honest dev implementation inspections.ts declares:
 * a local Python subprocess, fixture mode, no model key. What that produces is
 * a report that catalogues the media, reads the documents, and says plainly
 * which systems nothing examined - not a report that pretends it looked.
 */

export interface UploadState {
  error: string | null;
}

const MAX_FILES = 40;
const MAX_FILE_BYTES = 50 * 1024 * 1024;
const MAX_TOTAL_BYTES = 200 * 1024 * 1024;

const KIND_BY_EXT: Record<string, "photo" | "video" | "audio" | "document"> = {
  jpg: "photo",
  jpeg: "photo",
  png: "photo",
  webp: "photo",
  heic: "photo",
  heif: "photo",
  mp4: "video",
  mov: "video",
  webm: "video",
  m4v: "video",
  wav: "audio",
  mp3: "audio",
  m4a: "audio",
  aac: "audio",
  flac: "audio",
  ogg: "audio",
  txt: "document",
  pdf: "document",
};

function kindFor(name: string): "photo" | "video" | "audio" | "document" | null {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  return KIND_BY_EXT[ext] ?? null;
}

function optionalNumber(value: FormDataEntryValue | null): number | undefined {
  if (typeof value !== "string" || value.trim() === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

function optionalText(value: FormDataEntryValue | null): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

export async function startAnalysis(
  _prev: UploadState,
  formData: FormData,
): Promise<UploadState> {
  const files = formData
    .getAll("media")
    .filter((f): f is File => f instanceof File && f.size > 0);

  if (files.length === 0) {
    return { error: "Add at least one file. There is nothing to analyze without media." };
  }
  if (files.length > MAX_FILES) {
    return { error: `That is ${files.length} files; the limit is ${MAX_FILES} per analysis.` };
  }

  let total = 0;
  const prepared: { name: string; kind: "photo" | "video" | "audio" | "document"; bytes: Buffer }[] = [];
  for (const file of files) {
    if (file.size > MAX_FILE_BYTES) {
      return {
        error: `${file.name} is ${(file.size / 1024 / 1024).toFixed(0)}MB; the per-file limit is ${MAX_FILE_BYTES / 1024 / 1024}MB.`,
      };
    }
    total += file.size;
    if (total > MAX_TOTAL_BYTES) {
      return { error: `The upload exceeds ${MAX_TOTAL_BYTES / 1024 / 1024}MB in total.` };
    }
    const kind = kindFor(file.name);
    if (!kind) {
      return {
        error:
          `${file.name} is not a format this analyzes. ` +
          "Photographs (jpg, png, webp, heic), video (mp4, mov), audio (wav, mp3, m4a) " +
          "and documents (txt, pdf) are.",
      };
    }
    prepared.push({ name: file.name, kind, bytes: Buffer.from(await file.arrayBuffer()) });
  }

  let inspectionId: string;
  try {
    inspectionId = await createInspection({
      vin: optionalText(formData.get("vin")),
      askingPriceUsd: optionalNumber(formData.get("askingPriceUsd")),
      sellerStatedMileage: optionalNumber(formData.get("sellerStatedMileage")),
      listingYear: optionalNumber(formData.get("listingYear")),
      listingMake: optionalText(formData.get("listingMake")),
      listingModel: optionalText(formData.get("listingModel")),
      buyerNotes: optionalText(formData.get("buyerNotes")),
      files: prepared,
    });
    await analyse(inspectionId);
  } catch (cause) {
    // The true reason, not a soothing one. On a machine with no Python
    // environment this says exactly that and names the setup command.
    return { error: cause instanceof Error ? cause.message : String(cause) };
  }

  const token = issueGrant(inspectionId, "owner");
  (await cookies()).set({
    name: grantCookieName(inspectionId),
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: GRANT_COOKIE_MAX_AGE_SECONDS,
  });

  redirect(`/teaser/${inspectionId}`);
}
