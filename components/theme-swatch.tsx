// A miniature preview of a dashboard theme preset (a subset of presets.py),
// rendered as a tiny tile: surface, accent and a few series colors over the
// theme's window background.

export type Preset = {
  name: string;
  window: string;
  surface: string;
  text: string;
  accent: string;
  series: string[];
};

export function ThemeSwatch({ preset }: { preset: Preset }) {
  return (
    <figure className="tile overflow-hidden">
      <div className="p-3" style={{ background: preset.window }}>
        <div
          className="rounded-lg border p-3"
          style={{ background: preset.surface, borderColor: "rgba(0,0,0,0.06)" }}
        >
          <div
            className="text-[0.6rem] font-semibold uppercase tracking-wide"
            style={{ color: preset.text, opacity: 0.6 }}
          >
            Revenue
          </div>
          <div
            className="stat text-xl font-bold"
            style={{ color: preset.accent }}
          >
            48.2K
          </div>
          <div className="mt-2 flex items-end gap-1" style={{ height: 28 }}>
            {[60, 90, 45, 75, 35].map((h, i) => (
              <span
                key={i}
                className="flex-1 rounded-sm"
                style={{
                  height: `${h}%`,
                  background: preset.series[i % preset.series.length],
                }}
              />
            ))}
          </div>
        </div>
      </div>
      <figcaption className="border-t border-line px-3 py-2.5 text-sm font-medium">
        {preset.name}
      </figcaption>
    </figure>
  );
}
