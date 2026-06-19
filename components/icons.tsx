// Light stroke glyphs for feature tiles and the guide. 1.5px hairline strokes
// echo the plugin's soft-line chrome; they inherit currentColor.

type IconProps = { className?: string };

function Svg({ children, className }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const Icons = {
  indicator: (p: IconProps) => (
    <Svg {...p}>
      <path d="M4 14a8 8 0 0 1 16 0" />
      <path d="m12 14 4-3" />
      <circle cx="12" cy="14" r="1.2" />
    </Svg>
  ),
  chart: (p: IconProps) => (
    <Svg {...p}>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <rect x="7" y="11" width="3" height="6" />
      <rect x="12" y="7" width="3" height="10" />
      <rect x="17" y="13" width="3" height="4" />
    </Svg>
  ),
  pivot: (p: IconProps) => (
    <Svg {...p}>
      <rect x="4" y="4" width="16" height="16" rx="1.5" />
      <path d="M4 9h16M9 4v16" />
    </Svg>
  ),
  list: (p: IconProps) => (
    <Svg {...p}>
      <path d="M8 6h12M8 12h12M8 18h12" />
      <circle cx="4" cy="6" r="1" />
      <circle cx="4" cy="12" r="1" />
      <circle cx="4" cy="18" r="1" />
    </Svg>
  ),
  map: (p: IconProps) => (
    <Svg {...p}>
      <path d="m9 5-5 2v12l5-2 6 2 5-2V5l-5 2-6-2Z" />
      <path d="M9 5v12M15 7v12" />
    </Svg>
  ),
  selector: (p: IconProps) => (
    <Svg {...p}>
      <rect x="4" y="7" width="16" height="10" rx="2" />
      <path d="m9 11 3 3 3-3" />
    </Svg>
  ),
  text: (p: IconProps) => (
    <Svg {...p}>
      <path d="M6 6h12M12 6v12M9 18h6" />
    </Svg>
  ),
  image: (p: IconProps) => (
    <Svg {...p}>
      <rect x="4" y="5" width="16" height="14" rx="2" />
      <circle cx="9" cy="10" r="1.5" />
      <path d="m5 17 4-4 3 3 3-3 4 4" />
    </Svg>
  ),
  header: (p: IconProps) => (
    <Svg {...p}>
      <rect x="4" y="5" width="16" height="6" rx="1.5" />
      <path d="M4 15h10M4 19h7" />
    </Svg>
  ),
  crossfilter: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="7" cy="7" r="3" />
      <circle cx="17" cy="17" r="3" />
      <path d="M10 7h4a3 3 0 0 1 3 3v4M7 10v4a3 3 0 0 0 3 3h4" />
    </Svg>
  ),
  theme: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 4a8 8 0 0 0 0 16 4 4 0 0 0 0-8 4 4 0 0 1 0-8Z" />
    </Svg>
  ),
  export: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 15V4m0 0L8 8m4-4 4 4" />
      <path d="M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" />
    </Svg>
  ),
  publish: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 3a9 9 0 1 0 9 9" />
      <path d="M3.5 9h17M3.5 15h13" />
      <path d="M12 3c2.5 2.4 3.8 5.6 3.8 9S14.5 18.6 12 21M12 3C9.5 5.4 8.2 8.6 8.2 12" />
      <path d="m17 6 3-3m0 0h-2.5M20 3v2.5" />
    </Svg>
  ),
};

export type IconName = keyof typeof Icons;
