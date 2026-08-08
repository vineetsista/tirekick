import { rmSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { afterAll, describe, expect, it, vi } from "vitest";

/**
 * Two uploads must never land in one directory.
 *
 * The id was `insp_${randomUUID().slice(0, 8)}` - 32 bits - handed to
 * `mkdir(..., { recursive: true })`, which returns quietly when the directory is
 * already there. So a collision did not fail, it merged: the second upload's
 * media joined the first's, its manifest overwrote the first's, and since a
 * grant is an HMAC over the inspection id alone, either party's grant opened
 * both sets of photographs. The birthday bound puts even odds on that at around
 * 77,000 inspections.
 *
 * These tests drive the collision rather than arguing about its probability.
 * `randomUUID` is stubbed to repeat itself, which is the only way to exercise
 * the retry at all - a test that merely asserted "two ids differ" would pass
 * against the broken code every time it ran.
 */

vi.mock("node:crypto", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:crypto")>();
  return { ...actual, randomUUID: vi.fn(actual.randomUUID) };
});

const { randomUUID } = await import("node:crypto");
const { createInspection, inspectionDir } = await import("./inspections");

const created: string[] = [];
afterAll(() => {
  for (const id of created) rmSync(inspectionDir(id), { recursive: true, force: true });
});

async function upload(name: string): Promise<string> {
  const id = await createInspection({
    files: [{ name, kind: "photo", bytes: Buffer.from(name) }],
  });
  created.push(id);
  return id;
}

describe("an inspection directory is claimed, not assumed", () => {
  it("does not merge two uploads that draw the same id", async () => {
    const collided = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    const fresh = "11111111-2222-4333-8444-555555555555";

    // The first two draws are identical. Broken code writes both uploads into
    // one directory and returns the same id twice.
    vi.mocked(randomUUID)
      .mockReturnValueOnce(collided)
      .mockReturnValueOnce(collided)
      .mockReturnValueOnce(fresh);

    const first = await upload("front.jpg");
    const second = await upload("rear.jpg");

    expect(second).not.toBe(first);

    // And the directories are genuinely separate, which is the property the
    // buyer actually cares about. Equal ids would already have failed above;
    // this catches a "fix" that returns two ids pointing at one directory.
    expect(await readdir(join(inspectionDir(first), "media"))).toEqual(["front.jpg"]);
    expect(await readdir(join(inspectionDir(second), "media"))).toEqual(["rear.jpg"]);
  });

  it("uses the whole uuid, not a truncation of it", async () => {
    vi.mocked(randomUUID).mockReset();
    const id = await upload("odometer.jpg");

    // 32 hex characters. The old id carried eight, and eight is the entire
    // defect above - so the width is asserted rather than left as a comment
    // that a later tidy-up could shorten without anything noticing.
    expect(id).toMatch(/^insp_[0-9a-f]{32}$/);
  });
});
