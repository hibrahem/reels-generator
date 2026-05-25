import { useRef } from "react";
import { fmtClock } from "../lib/api";

/**
 * Dual-handle range slider for trimming a reel's in/out points.
 *
 * The track is zoomed to a padded window around the reel (not the whole video) so a short
 * clip inside a long course video is still draggable with precision. Dragging a handle calls
 * `onChange` continuously and `onScrub` so the player can seek to the frame under the handle.
 */
export function TrimSlider({
  windowStart,
  windowEnd,
  start,
  end,
  minGap = 0.1,
  onChange,
  onScrub,
}: {
  windowStart: number;
  windowEnd: number;
  start: number;
  end: number;
  /** Minimum allowed clip length, in seconds. */
  minGap?: number;
  onChange: (start: number, end: number) => void;
  /** Fired while dragging so the player can show the frame at the moving edge. */
  onScrub?: (t: number) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const span = Math.max(windowEnd - windowStart, 0.001);
  const pct = (t: number) => Math.max(0, Math.min(100, ((t - windowStart) / span) * 100));

  function timeAt(clientX: number): number {
    const rect = trackRef.current!.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return windowStart + ratio * span;
  }

  function beginDrag(which: "start" | "end") {
    return (e: React.PointerEvent) => {
      e.preventDefault();
      const move = (ev: PointerEvent) => {
        const t = timeAt(ev.clientX);
        if (which === "start") {
          const ns = Math.max(windowStart, Math.min(t, end - minGap));
          onChange(ns, end);
          onScrub?.(ns);
        } else {
          const ne = Math.min(windowEnd, Math.max(t, start + minGap));
          onChange(start, ne);
          onScrub?.(ne);
        }
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
      window.addEventListener("pointercancel", up);
    };
  }

  const handleCls =
    "absolute top-1/2 z-10 size-4 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize rounded-full " +
    "border-2 border-background bg-primary shadow ring-1 ring-primary/40 hover:scale-110 transition";

  return (
    <div className="select-none">
      <div
        ref={trackRef}
        className="relative h-8 w-full rounded-lg border border-border bg-muted/40"
      >
        {/* selected cut region (purple) */}
        <div
          className="absolute top-0 h-full rounded-md bg-primary/30"
          style={{ left: `${pct(start)}%`, width: `${Math.max(pct(end) - pct(start), 0)}%` }}
        />
        {/* start handle */}
        <div
          role="slider"
          aria-label="Reel start"
          aria-valuenow={start}
          onPointerDown={beginDrag("start")}
          className={handleCls}
          style={{ left: `${pct(start)}%` }}
        />
        {/* end handle */}
        <div
          role="slider"
          aria-label="Reel end"
          aria-valuenow={end}
          onPointerDown={beginDrag("end")}
          className={handleCls}
          style={{ left: `${pct(end)}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between font-mono text-[11px] text-muted-foreground">
        <span>{fmtClock(windowStart)}</span>
        <span className="text-primary">
          {fmtClock(start)} – {fmtClock(end)} · {(end - start).toFixed(1)}s
        </span>
        <span>{fmtClock(windowEnd)}</span>
      </div>
    </div>
  );
}
