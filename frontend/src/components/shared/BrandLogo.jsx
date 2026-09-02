import { BRAND } from "../../lib/brandConfig";

const VARIANT_CLASS = {
  sidebar: "h-12 w-auto max-w-[14rem] object-contain object-left",
  login: "h-20 w-auto max-w-xs object-contain",
  splash: "h-24 w-auto max-w-sm object-contain",
  header: "h-10 w-auto max-w-[12rem] object-contain",
};

/**
 * Official The Hindu wordmark. On dark surfaces (`darkBackground`), invert to a
 * light mark. On light surfaces, show the asset as-is.
 */
export default function BrandLogo({
  variant = "sidebar",
  className = "",
  darkBackground = false,
  testId,
}) {
  const src = darkBackground
    ? BRAND.logoDarkUrl || BRAND.logoUrl
    : BRAND.logoUrl || BRAND.logoDarkUrl;

  if (!src) {
    return (
      <span
        className={`font-serif font-bold tracking-wider ${darkBackground ? "text-white" : ""} ${className}`.trim()}
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
      className={`rounded-lg ${VARIANT_CLASS[variant] || VARIANT_CLASS.sidebar} ${darkBackground ? "brightness-0 invert" : ""} ${className}`.trim()}
      data-testid={testId}
    />
  );
}
