/** Shield mark aligned with Ma-WAF login branding. */
export default function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 56 56"
      width={56}
      height={56}
      aria-hidden
    >
      <defs>
        <linearGradient id="msShield" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#1a6db5" />
          <stop offset="100%" stopColor="#0b4f8a" />
        </linearGradient>
      </defs>
      <path
        fill="url(#msShield)"
        d="M28 4c8.5 3.2 16 4.2 20 4.8v18.2c0 12.4-7.8 21.6-20 25-12.2-3.4-20-12.6-20-25V8.8C12 8.2 19.5 7.2 28 4z"
      />
      <path
        fill="#fff"
        d="M18.5 28.2l5.2-12.4h4.2l-3.2 7.2h7.6l-7.8 13.4h-4.1l4.8-8.2H18.5z"
        opacity={0.95}
      />
      <path
        fill="#7eb6ef"
        d="M30.2 15.8h4.1l5.2 12.4h-4.4l-1.1-2.8h-5.2l2.1-4.8 1.3 3.2h2.6l-2.6-7.8z"
        opacity={0.9}
      />
    </svg>
  );
}
