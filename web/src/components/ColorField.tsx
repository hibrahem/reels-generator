import { useState } from "react";
import { Popover } from "radix-ui";
import { RgbaColorPicker } from "react-colorful";

import { assToRgba, rgbaToAss, type Rgba } from "@/lib/assColor";
import { cn } from "@/lib/utils";

/**
 * A colour field for the schema-driven config editor.
 *
 * Renders three things kept in sync:
 *   - a swatch button that opens a popover with a hue/saturation + alpha picker
 *     (react-colorful's {@link RgbaColorPicker}), and
 *   - a still-editable raw `&HAABBGGRR` text input for power users.
 *
 * The picker speaks standard RGBA (opacity 0..1); the stored/edited value is
 * ASS (`&HAABBGGRR`, reversed bytes + inverted alpha). All conversion goes
 * through `@/lib/assColor`, so the value written back on save is valid ASS and
 * the libass renderer is unchanged.
 *
 * The Radix Popover gives us accessible, keyboard-usable open/close behaviour:
 * it closes on outside-click and Esc, and manages focus + ARIA attributes.
 */
export function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  /** Raw ASS colour string, e.g. "&H00FFFFFF". May be null. */
  value: string | null;
  /** Called with the new raw ASS string (or null when cleared). */
  onChange: (v: string | null) => void;
}) {
  const [open, setOpen] = useState(false);

  const raw = value ?? "";
  const rgba = assToRgba(raw);
  // A CSS colour for the swatch; falls back to a transparent checkerboard tone
  // when the raw text isn't yet a valid ASS colour.
  const swatchCss = rgba ? `rgba(${rgba.r}, ${rgba.g}, ${rgba.b}, ${rgba.a})` : undefined;

  const handlePickerChange = (next: Rgba) => {
    onChange(rgbaToAss(next));
  };

  return (
    <label className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <Popover.Root open={open} onOpenChange={setOpen}>
          <Popover.Trigger asChild>
            <button
              type="button"
              aria-label={`Pick colour for ${label}`}
              className={cn(
                "relative size-8 shrink-0 overflow-hidden rounded-lg border border-input",
                "bg-[conic-gradient(#0000_90deg,#80808033_0_180deg,#0000_0_270deg,#80808033_0)] bg-[length:10px_10px]",
                "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              )}
            >
              {/* The colour layer sits over a checkerboard so alpha is visible. */}
              <span
                aria-hidden
                className="absolute inset-0"
                style={swatchCss ? { backgroundColor: swatchCss } : undefined}
              />
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              sideOffset={6}
              align="end"
              className="z-50 rounded-xl border border-border bg-popover p-3 shadow-lg outline-none"
            >
              <RgbaColorPicker
                color={rgba ?? { r: 255, g: 255, b: 255, a: 1 }}
                onChange={handlePickerChange}
              />
              <Popover.Arrow className="fill-border" />
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
        <input
          type="text"
          value={raw}
          placeholder={value == null ? "null" : "&H00FFFFFF"}
          spellCheck={false}
          onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
          className={cn(
            "w-40 rounded-lg border border-input bg-background px-2 py-1 font-mono text-sm",
            "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
          )}
        />
      </div>
    </label>
  );
}
