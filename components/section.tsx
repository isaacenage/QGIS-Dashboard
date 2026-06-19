import { ReactNode } from "react";

export function Section({
  id,
  eyebrow,
  title,
  lead,
  children,
  className = "",
}: {
  id?: string;
  eyebrow?: string;
  title?: ReactNode;
  lead?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`mx-auto max-w-6xl px-5 py-20 ${className}`}>
      {(eyebrow || title || lead) && (
        <div className="max-w-2xl">
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          {title && (
            <h2 className="display mt-4 text-3xl text-ink sm:text-4xl">{title}</h2>
          )}
          {lead && <p className="mt-4 text-lg leading-relaxed text-muted">{lead}</p>}
        </div>
      )}
      {children}
    </section>
  );
}
