"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Single source of truth for every button in the app.
 *
 * Replaces the previous version, which returned inline style objects and so
 * could not express hover/focus/active states. Pages had worked around that by
 * hand-rolling their own oversized inline-styled buttons (the kiosk had 24px
 * padding with 24px text), which is why the UI looked inconsistent.
 *
 * Sizes are deliberately restrained. `kiosk` exists for genuine touch targets
 * and is the only large option — it meets the 44px minimum for touch without
 * ballooning to banner size.
 */
const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "rounded-lg font-semibold select-none",
    "transition-all duration-150 ease-out",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
    "focus-visible:ring-indigo-500 focus-visible:ring-offset-[#0a0a0f]",
    "disabled:pointer-events-none disabled:opacity-45",
    "active:translate-y-px",
    "[&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-sm shadow-indigo-500/25 hover:shadow-md hover:shadow-indigo-500/40 hover:-translate-y-px",
        secondary:
          "bg-white/[0.06] text-slate-100 border border-white/10 hover:bg-white/[0.1] hover:border-white/20",
        success:
          "bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-sm shadow-emerald-500/25 hover:shadow-md hover:shadow-emerald-500/40 hover:-translate-y-px",
        danger:
          "bg-gradient-to-br from-red-500 to-red-700 text-white shadow-sm shadow-red-500/25 hover:shadow-md hover:shadow-red-500/40 hover:-translate-y-px",
        warning:
          "bg-gradient-to-br from-amber-500 to-amber-600 text-slate-950 shadow-sm shadow-amber-500/25 hover:shadow-md hover:shadow-amber-500/40 hover:-translate-y-px",
        outline:
          "bg-transparent text-slate-300 border border-white/15 hover:bg-white/[0.06] hover:text-white hover:border-white/25",
        ghost:
          "bg-transparent text-slate-400 hover:bg-white/[0.06] hover:text-slate-100",
        link:
          "bg-transparent text-indigo-400 underline-offset-4 hover:underline hover:text-indigo-300 shadow-none",
      },
      size: {
        sm: "h-8 px-3 text-xs [&_svg]:size-3.5",
        md: "h-9 px-4 text-sm [&_svg]:size-4",
        lg: "h-11 px-6 text-[0.9375rem] [&_svg]:size-4",
        kiosk: "h-14 px-8 text-base [&_svg]:size-5",
        icon: "size-9 p-0 [&_svg]:size-4",
        "icon-sm": "size-8 p-0 [&_svg]:size-3.5",
      },
      block: {
        true: "w-full",
        false: "",
      },
    },
    defaultVariants: { variant: "primary", size: "md", block: false },
  }
);

export interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "color">,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
  /** Rendered before the label; hidden while loading so width stays stable. */
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, size, block, isLoading = false, icon, children, disabled, ...props },
    ref
  ) => (
    <button
      ref={ref}
      // aria-busy tells screen readers the control is working; the visual
      // spinner alone conveys nothing to assistive tech.
      aria-busy={isLoading || undefined}
      disabled={disabled || isLoading}
      className={cn(buttonVariants({ variant, size, block }), className)}
      {...props}
    >
      {isLoading ? (
        <span
          aria-hidden="true"
          className="size-4 animate-spin rounded-full border-2 border-current/30 border-t-current"
        />
      ) : (
        icon
      )}
      {children}
    </button>
  )
);
Button.displayName = "Button";

export { buttonVariants };
export default Button;
