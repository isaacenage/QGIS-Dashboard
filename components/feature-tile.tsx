import { Icons, IconName } from "./icons";

export function FeatureTile({
  icon,
  name,
  role,
  children,
}: {
  icon: IconName;
  name: string;
  role?: string;
  children: React.ReactNode;
}) {
  const Glyph = Icons[icon];
  return (
    <div className="tile group flex flex-col p-5 transition-transform duration-200 hover:-translate-y-0.5">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-[10px] bg-accent/8 text-accent">
          <Glyph className="h-5 w-5" />
        </span>
        <div>
          <h3 className="font-semibold leading-tight">{name}</h3>
          {role && (
            <p className="stat text-[0.68rem] uppercase tracking-wide text-faint">
              {role}
            </p>
          )}
        </div>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-muted">{children}</p>
    </div>
  );
}
