import { BRAND } from "../../lib/brandConfig";

const VARIANT_CLASS = {
  sidebar: "h-12 w-auto max-w-[14rem] object-contain object-left",
  login: "h-20 w-auto max-w-xs object-contain",
  splash: "h-24 w-auto max-w-sm object-contain",
  header: "h-10 w-auto max-w-[12rem] object-contain",
};

/**
 * Official The Hindu wordmark (blue type on black). Displayed as-is — the
 * asset already includes its own black field, so it is not inverted or badged.
 */
export default function BrandLogo({
  variant = "sidebar",
  className = "",
  darkBackground: _darkBackground = true,
  testId,
}) {
  const src = BRAND.logoDarkUrl || BRAND.logoUrl;

  if (!src) {
    return (
      <span
        className={`font-serif font-bold tracking-wider ${className}`}
        data-testid={testId}
      >
        {BRAND.name}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={BRAND.logoAlt}
      className={`rounded-lg ${VARIANT_CLASS[variant] || VARIANT_CLASS.sidebar} ${className}`.trim()}
      data-testid={testId}
    />
  );
}
