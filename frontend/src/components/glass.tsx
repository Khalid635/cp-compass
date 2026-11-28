/* GlassyUI-adapted glass chrome (premium-apply batch).
   Why adapted, not a verbatim copy: GlassyUI's registry components
   (glass-panel / glass-button / glass-surface) run on a WebGL scene
   engine — scene-renderer.ts alone is 2,211 lines, liquid.css 5,458,
   plus new deps (clsx, @radix-ui/react-slot) — far too heavy to carry
   for chrome-only use (cards, panels, navbar — never data-dense tables).
   These components carry GlassyUI's look in Rung tokens instead,
   grounded in its liquid.css values: backdrop blur 14px, saturate 1.4,
   a 1px rim (top highlight + border), a translucent surface tint, and
   no backdrop-filter at all under prefers-reduced-transparency
   (liquid.css kills the filter there too). GlassyUI is MIT-licensed;
   the adaptation keeps its material language, not its engine. */
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';

export function GlassPanel({
  children,
  className = '',
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children?: ReactNode }) {
  return (
    <div className={`glass-panel ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function GlassButton({
  children,
  className = '',
  variant = 'primary',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children?: ReactNode;
  variant?: 'primary' | 'ghost';
}) {
  return (
    <button
      type="button"
      className={`glass-btn ${variant === 'ghost' ? 'glass-btn--ghost' : ''} ${className}`}
      {...rest}
    >
      <span className="glass-btn__label">{children}</span>
    </button>
  );
}
