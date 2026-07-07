function initial(name: string): string {
  return (name.trim()[0] ?? "?").toUpperCase();
}

export function CompanyLogo({
  name,
  logoUrl,
  size = 32,
}: {
  name: string;
  logoUrl?: string | null;
  size?: number;
}) {
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={`${name} logo`}
        className="flex-none rounded-lg object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="flex flex-none items-center justify-center rounded-lg bg-brand-tint font-bold text-brand"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {initial(name)}
    </div>
  );
}
