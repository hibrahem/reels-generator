/**
 * Conversion between ASS subtitle colour codes and RGBA.
 *
 * ASS (Advanced SubStation Alpha) stores colours as `&HAABBGGRR`, which has
 * two gotchas that make a naive hex parse wrong:
 *
 *   1. **Byte order is reversed vs RGB.** The colour bytes are `BB GG RR`
 *      (blue, green, red) — NOT `RR GG BB`. So `&H00FF8000` is
 *      `BB=FF, GG=80, RR=00` → blue=255, green=128, red=0.
 *
 *   2. **The leading `AA` byte is TRANSPARENCY, not opacity.** `00` means
 *      fully opaque and `FF` means fully transparent — inverted from the
 *      usual RGBA alpha channel. We expose `a` as standard *opacity*
 *      (0 = transparent, 1 = opaque), so the conversion inverts on both ways.
 *
 * The `AA` byte is optional in ASS: a 6-hex-digit value (`&HBBGGRR`) is
 * treated as fully opaque (transparency `00`).
 *
 * Examples (all round-trip):
 *   assToRgba("&H00FFFFFF") → { r: 255, g: 255, b: 255, a: 1 }      // opaque white
 *   assToRgba("&H0000D7FF") → { r: 255, g: 215, b: 0,   a: 1 }      // opaque gold (RR=FF, GG=D7, BB=00)
 *   assToRgba("&H90000000") → { r: 0,   g: 0,   b: 0,   a: ~0.435 } // ~56%-transparent black (AA=90)
 *   assToRgba("&HFF0000FF") → { r: 255, g: 0,   b: 0,   a: 1 }      // opaque red
 *
 *   rgbaToAss({ r: 255, g: 255, b: 255, a: 1 })     → "&H00FFFFFF"
 *   rgbaToAss({ r: 0, g: 0, b: 0, a: 0.435 })       → "&H90000000"
 */

export interface Rgba {
  /** Red channel, 0..255. */
  r: number;
  /** Green channel, 0..255. */
  g: number;
  /** Blue channel, 0..255. */
  b: number;
  /** Opacity, 0..1 (0 = fully transparent, 1 = fully opaque). */
  a: number;
}

/** Two-digit uppercase hex for a byte value (clamped to 0..255). */
function toHexByte(n: number): string {
  const clamped = Math.max(0, Math.min(255, Math.round(n)));
  return clamped.toString(16).toUpperCase().padStart(2, "0");
}

/** Clamp a channel value to an integer in 0..255. */
function clampByte(n: number): number {
  return Math.max(0, Math.min(255, Math.round(n)));
}

/**
 * Parse an ASS colour string (`&HAABBGGRR` or `&HBBGGRR`) into RGBA with
 * standard opacity. Robust to `&H`/`&h` prefix casing, a missing prefix,
 * surrounding whitespace, and 6- or 8-hex-digit bodies.
 *
 * Returns `null` for input that isn't a recognisable ASS colour, so callers
 * can keep the raw text editable without crashing the picker.
 */
export function assToRgba(ass: string): Rgba | null {
  if (typeof ass !== "string") return null;
  // Strip whitespace and an optional &H / &h prefix.
  const body = ass.trim().replace(/^&[hH]/, "");
  if (!/^[0-9a-fA-F]+$/.test(body)) return null;

  let hex: string;
  if (body.length === 6) {
    // No alpha byte → fully opaque (transparency 00).
    hex = "00" + body;
  } else if (body.length === 8) {
    hex = body;
  } else {
    return null;
  }

  const aa = parseInt(hex.slice(0, 2), 16); // transparency
  const bb = parseInt(hex.slice(2, 4), 16); // blue
  const gg = parseInt(hex.slice(4, 6), 16); // green
  const rr = parseInt(hex.slice(6, 8), 16); // red

  return {
    r: rr,
    g: gg,
    b: bb,
    // Invert transparency → opacity.
    a: (255 - aa) / 255,
  };
}

/**
 * Serialise RGBA (with standard opacity) back to an ASS `&HAABBGGRR` string.
 * Inverts opacity → transparency and reverses the colour byte order, so the
 * output is exactly what the libass renderer expects.
 */
export function rgbaToAss({ r, g, b, a }: Rgba): string {
  const opacity = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 1;
  const aa = toHexByte((1 - opacity) * 255); // opacity → transparency
  const bb = toHexByte(clampByte(b));
  const gg = toHexByte(clampByte(g));
  const rr = toHexByte(clampByte(r));
  return `&H${aa}${bb}${gg}${rr}`;
}

/** True if a field value looks like an ASS colour we can render in the picker. */
export function isAssColor(value: unknown): value is string {
  return typeof value === "string" && assToRgba(value) !== null;
}
