import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, fmtClock, type TranscriptSegment, type TranscriptWord } from "../lib/api";

export function TranscriptView({
  segments,
  currentTime,
  onSeek,
  selStart,
  selEnd,
  onSetStart,
  onSetEnd,
  videoId,
}: {
  segments: TranscriptSegment[];
  currentTime: number;
  onSeek: (t: number) => void;
  /** When provided, the view enters selection mode: each row gets set-start / set-end actions. */
  selStart?: number;
  selEnd?: number;
  onSetStart?: (t: number) => void;
  onSetEnd?: (t: number) => void;
  /** When provided, the view gains an "Edit" toggle for word-level text correction. */
  videoId?: string;
}) {
  const selecting = onSetStart != null && onSetEnd != null;
  const editable = videoId != null;
  const qc = useQueryClient();

  const [editing, setEditing] = useState(false);
  // Draft is a deep-ish copy of segments while editing; only word `text` is mutated.
  const [draft, setDraft] = useState<TranscriptSegment[]>(segments);

  // Re-seed the draft whenever the source transcript changes (or edit mode toggles on),
  // so we never edit against a stale copy after an invalidation.
  useEffect(() => {
    if (!editing) setDraft(segments);
  }, [segments, editing]);

  const save = useMutation({
    mutationFn: () => api.editTranscript(videoId!, draft),
    onSuccess: () => {
      setEditing(false);
      void qc.invalidateQueries({ queryKey: ["transcript", videoId] });
    },
  });

  const startEditing = () => {
    setDraft(segments);
    setEditing(true);
  };

  const setWordText = (segIdx: number, wordIdx: number, text: string) => {
    setDraft((prev) =>
      prev.map((seg, si) =>
        si !== segIdx
          ? seg
          : {
              ...seg,
              // Keep each word's start/end/probability; only text changes.
              words: seg.words.map((w, wi) => (wi !== wordIdx ? w : { ...w, text })),
              // Keep the convenience segment text in sync with its words.
              text: seg.words.map((w, wi) => (wi === wordIdx ? text : w.text)).join(" "),
            },
      ),
    );
  };

  return (
    <div className="space-y-2">
      {editable && (
        <div className="flex items-center justify-end gap-2">
          {editing ? (
            <>
              {save.isError && (
                <span className="mr-auto text-[11px] text-destructive">
                  {(save.error as Error).message}
                </span>
              )}
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setDraft(segments);
                  save.reset();
                }}
                className="rounded bg-muted px-2 py-1 text-xs text-muted-foreground hover:bg-muted/70"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={save.isPending}
                onClick={() => save.mutate()}
                className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {save.isPending ? "Saving…" : "Save"}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={startEditing}
              className="rounded bg-muted px-2 py-1 text-xs text-muted-foreground hover:bg-primary/20 hover:text-primary"
            >
              Edit transcript
            </button>
          )}
        </div>
      )}

      <div className="max-h-[420px] overflow-y-auto rounded-xl border border-border">
        {(editing ? draft : segments).map((seg, i) => {
          const playing = currentTime >= seg.start && currentTime < seg.end;
          // A segment is inside the selected cut when it overlaps [selStart, selEnd].
          const inRange =
            selecting &&
            selStart != null &&
            selEnd != null &&
            seg.end > selStart &&
            seg.start < selEnd;
          return (
            <div
              key={i}
              dir="rtl"
              className={`flex w-full items-start gap-3 border-b border-border/70 px-3 py-2 text-right transition last:border-0 ${
                inRange ? "bg-primary/15" : playing ? "bg-primary/10" : "hover:bg-muted/40"
              }`}
            >
              <button
                type="button"
                onClick={() => onSeek(seg.start)}
                dir="ltr"
                title="Seek here"
                className={`mt-0.5 shrink-0 font-mono text-[11px] ${
                  playing ? "text-primary" : "text-muted-foreground"
                } hover:text-foreground`}
              >
                {fmtClock(seg.start)}
              </button>
              {editing ? (
                <WordEditor
                  words={seg.words}
                  onChange={(wordIdx, text) => setWordText(i, wordIdx, text)}
                  fallbackText={seg.text}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => onSeek(seg.start)}
                  className={`flex-1 text-right text-sm ${
                    playing || inRange ? "text-foreground" : "text-muted-foreground"
                  } hover:text-foreground`}
                >
                  {seg.text.trim()}
                </button>
              )}
              {selecting && !editing && (
                <div dir="ltr" className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    onClick={() => onSetStart!(seg.start)}
                    title="Set reel start to this segment"
                    className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-primary/20 hover:text-primary"
                  >
                    start
                  </button>
                  <button
                    type="button"
                    onClick={() => onSetEnd!(seg.end)}
                    title="Set reel end to this segment"
                    className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-primary/20 hover:text-primary"
                  >
                    end
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Editable row of words. Each word is an input sized to its content; editing the text leaves the
 * word's start/end untouched (handled by the parent), so caption karaoke timing survives the edit.
 * Falls back to a single input on the segment text when a segment has no word-level timings.
 */
function WordEditor({
  words,
  onChange,
  fallbackText,
}: {
  words: TranscriptWord[];
  onChange: (wordIdx: number, text: string) => void;
  fallbackText: string;
}) {
  if (words.length === 0) {
    return (
      <input
        dir="auto"
        defaultValue={fallbackText.trim()}
        disabled
        title="This segment has no word-level timings to edit"
        className="flex-1 rounded border border-border bg-muted/40 px-2 py-1 text-right text-sm text-muted-foreground"
      />
    );
  }
  return (
    <div dir="rtl" className="flex flex-1 flex-wrap justify-end gap-1">
      {words.map((w, wi) => (
        <input
          key={wi}
          dir="auto"
          value={w.text}
          onChange={(e) => onChange(wi, e.target.value)}
          title={`${fmtClock(w.start)} – ${fmtClock(w.end)}`}
          size={Math.max(w.text.length, 1)}
          className="rounded border border-border bg-background px-1 py-0.5 text-center text-sm text-foreground focus:border-primary focus:outline-none"
        />
      ))}
    </div>
  );
}
