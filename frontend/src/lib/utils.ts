import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, letting later Tailwind utilities win over earlier ones.
 *
 * `clsx` handles conditionals/arrays; `twMerge` resolves genuine Tailwind
 * conflicts (e.g. "px-4 px-6" -> "px-6") which plain concatenation cannot.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
