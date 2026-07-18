/**
 * Reels Studio logomark: a 9:16 film frame with a play notch, drawn in the
 * brand amber. Used in the header, empty thumbnails, and (as a data URI) the favicon.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect
        x="5.5"
        y="2.5"
        width="13"
        height="19"
        rx="3"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path d="M10.5 9.2c0-.78.85-1.26 1.52-.86l4.06 2.44c.65.39.65 1.33 0 1.72l-4.06 2.44c-.67.4-1.52-.08-1.52-.86V9.2z" fill="currentColor" />
    </svg>
  );
}
