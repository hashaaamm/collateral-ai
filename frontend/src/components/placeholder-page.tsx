export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <h1 className="text-[26px] font-bold tracking-[-0.03em] text-ink">
        {title}
      </h1>
      <div className="mt-6 rounded-2xl border border-dashed border-hairline bg-surface p-12 text-center text-sm text-mute">
        Coming soon
      </div>
    </div>
  );
}
