import type { ReactNode } from "react";
import {
  ArrowDownLeft,
  ArrowRight,
  ArrowSquareOut,
  ArrowsLeftRight,
  ArrowUpRight,
  Buildings,
  CalendarCheck,
  Check,
  CheckCircle,
  CircleNotch,
  FilePdf,
  FileText,
  Flag,
  Image as ImageIcon,
  Layout,
  ListChecks,
  MagicWand,
  Newspaper,
  PaperPlaneTilt,
  SignOut,
  Sparkle,
  SquaresFour,
  Stack,
  UploadSimple,
} from "@phosphor-icons/react";

const LOGIN = "/login";
const asset = (name: string) => `/landing/${name}`;

/** Public marketing landing page (recreated from the Landing.dc.html design). */
export function LandingPage() {
  return (
    <div className="min-h-dvh bg-surface text-ink [scroll-behavior:smooth]">
      <Nav />
      <Hero />
      <ValueStatement />
      <HowItWorks />
      <SourcesBand />
      <Features />
      <TemplatesBand />
      <FinalCta />
      <Footer />
    </div>
  );
}

/* ------------------------------------------------------------------ Nav --- */

function Nav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-black/[.06] bg-white/[.78] backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex h-[52px] max-w-[1024px] items-center gap-7 px-6">
        <a href="#top" className="mr-auto flex items-center gap-[9px]">
          <LogoTile size={24} radius={7} icon={14} />
          <span className="text-[15px] font-bold tracking-[-0.02em] text-ink">
            Collateral AI
          </span>
        </a>
        <div className="flex items-center gap-6 text-[13px] font-medium">
          <a href="#how" className="hidden text-[#55555e] hover:text-ink sm:inline">
            How it works
          </a>
          <a href="#features" className="hidden text-[#55555e] hover:text-ink sm:inline">
            Why Collateral
          </a>
          <a
            href={LOGIN}
            className="rounded-full bg-ink px-4 py-[7px] font-semibold text-white hover:bg-[#333]"
          >
            Get started
          </a>
        </div>
      </div>
    </nav>
  );
}

function LogoTile({
  size = 42,
  radius = 12,
  icon = 24,
}: {
  size?: number;
  radius?: number;
  icon?: number;
}) {
  return (
    <div
      className="flex flex-none items-center justify-center bg-brand shadow-[0_10px_26px_rgba(91,91,214,.45)]"
      style={{ width: size, height: size, borderRadius: radius }}
    >
      <Stack weight="fill" size={icon} className="text-white" />
    </div>
  );
}

/* ----------------------------------------------------------------- Hero --- */

function Hero() {
  return (
    <header
      id="top"
      className="px-6 pt-24 text-center [animation:heroUp_.7s_cubic-bezier(.2,.7,.2,1)_both]"
    >
      <div className="mb-7 flex items-center justify-center gap-[11px]">
        <LogoTile />
        <span className="text-[21px] font-extrabold tracking-[-0.02em]">
          Collateral AI
        </span>
      </div>
      <h1 className="mx-auto max-w-[820px] text-[clamp(44px,7vw,76px)] font-extrabold leading-[1.02] tracking-[-0.045em] text-balance">
        Marketing collateral. On autopilot.
      </h1>
      <p className="mx-auto mt-[26px] max-w-[580px] text-[20px] leading-[1.5] text-[#55555e] text-pretty">
        Give it your company&rsquo;s documents — and your prospect&rsquo;s.
        Collateral AI writes tailored, factually-grounded B2B materials that
        speak to both sides of the deal.
      </p>
      <div className="mt-[34px] flex flex-wrap justify-center gap-[14px]">
        <a
          href={LOGIN}
          className="rounded-full bg-brand px-7 py-[13px] text-[15.5px] font-semibold text-white hover:bg-brand-hover"
        >
          Get started
        </a>
        <a
          href="#how"
          className="rounded-full border border-[#d8d8de] px-7 py-[13px] text-[15.5px] font-semibold text-ink hover:bg-nav-hover"
        >
          See how it works
        </a>
      </div>
      <DashboardMock />
    </header>
  );
}

/** The framed dashboard screenshot below the hero copy. */
function DashboardMock() {
  return (
    <div className="mx-auto mt-[72px] max-w-[1024px] overflow-hidden rounded-t-[18px] border border-b-0 border-hairline bg-surface text-left shadow-[0_40px_120px_-32px_rgba(30,30,80,.28)]">
      <div className="flex">
        {/* Sidebar */}
        <div className="hidden w-[208px] flex-none flex-col border-r border-hairline bg-surface px-3 pb-[14px] pt-4 sm:flex">
          <div className="flex items-center gap-2 px-[6px]">
            <div className="flex size-[26px] items-center justify-center rounded-lg bg-brand">
              <Stack weight="fill" size={14} className="text-white" />
            </div>
            <span className="text-sm font-bold tracking-[-0.02em]">
              Collateral AI
            </span>
            <span className="rounded-full border border-hairline px-[6px] py-[2px] text-[8.5px] font-semibold text-mute">
              MVP
            </span>
          </div>
          <div className="mx-[6px] mb-2 mt-[18px] text-[10px] font-semibold uppercase tracking-[.05em] text-faint">
            Workspace
          </div>
          <div className="flex flex-col gap-[2px]">
            <MockNav active icon={<SquaresFour size={16} className="text-brand" />}>
              Dashboard
            </MockNav>
            <MockNav icon={<Buildings size={16} />}>Companies</MockNav>
            <MockNav icon={<MagicWand size={16} />}>Create Material</MockNav>
            <MockNav icon={<ListChecks size={16} />}>Marketing Requests</MockNav>
            <MockNav icon={<Layout size={16} />}>Templates</MockNav>
          </div>
          <div className="mt-auto flex items-center gap-2 rounded-[10px] bg-rail p-2">
            <div className="flex size-[26px] flex-none items-center justify-center rounded-[7px] bg-brand-tint text-[10.5px] font-bold text-brand">
              JP
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[11.5px] font-semibold">
                Julie Plusquin
              </div>
              <div className="text-[9.5px] text-mute">Editor</div>
            </div>
            <SignOut size={13} className="text-mute" />
          </div>
        </div>
        {/* Main */}
        <div className="min-w-0 flex-1 bg-page px-7 pb-[26px] pt-6">
          <div className="text-[11.5px] text-mute">Wednesday, July 6</div>
          <div className="mt-[3px] text-[22px] font-bold tracking-[-0.03em]">
            Good morning, Julie
          </div>
          <div className="mt-[18px] grid grid-cols-2 gap-3 md:grid-cols-4">
            <MockStat label="Companies" value="6" delta="+2 this week" deltaClass="text-success" icon={<Buildings size={13} className="text-[#b7b7c0]" />} />
            <MockStat label="Documents processed" value="18" delta="2 processing" deltaClass="text-mute" icon={<FileText size={13} className="text-[#b7b7c0]" />} />
            <MockStat label="Materials generated" value="11" delta="+4 this week" deltaClass="text-success" icon={<MagicWand size={13} className="text-[#b7b7c0]" />} />
            <MockStat label="Needs review" value="2" delta="Awaiting approval" deltaClass="text-warning" icon={<Flag size={13} className="text-[#b7b7c0]" />} />
          </div>
          <div className="mt-[14px] grid grid-cols-1 items-start gap-[14px] lg:grid-cols-[1.55fr_1fr]">
            {/* Recent materials */}
            <div className="overflow-hidden rounded-xl border border-hairline bg-surface">
              <div className="flex items-center justify-between border-b border-[#f0f0f2] px-4 py-3">
                <span className="text-[13px] font-semibold">Recent materials</span>
                <span className="text-[11.5px] font-semibold text-brand">View all</span>
              </div>
              <MockRow title="Reliability for Every Booking" status="completed" />
              <MockRow title="Cutting MTTR at Scale" status="processing" />
              <MockRow title="Payments Observability Brief" status="review" last />
            </div>
            {/* Quick start */}
            <div className="rounded-xl border border-hairline bg-surface px-4 py-[14px]">
              <div className="text-[13px] font-semibold">Quick start</div>
              <div className="mt-[3px] text-[11px] leading-[1.5] text-mute">
                Go from company context to a finished article in three steps.
              </div>
              <div className="mt-[11px] flex flex-col gap-2">
                <QuickStep bg="bg-success-soft" icon={<Check weight="bold" size={11} className="text-success" />} title="Add companies" sub="6 profiles ready" />
                <QuickStep bg="bg-warning-soft" icon={<CircleNotch size={11} className="text-warning" />} title="Upload documents" sub="2 still processing" />
                <QuickStep bg="bg-brand-soft" icon={<span className="text-[10.5px] font-bold text-brand">3</span>} title="Generate material" sub="Sender → receiver article" />
              </div>
              <div className="mt-[13px] flex items-center justify-center gap-[6px] rounded-[9px] bg-brand p-[9px] text-xs font-semibold text-white">
                <MagicWand weight="fill" size={13} />
                Create Material
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MockNav({
  children,
  icon,
  active,
}: {
  children: ReactNode;
  icon: ReactNode;
  active?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-[9px] rounded-[9px] px-[9px] py-2 text-[12.5px] ${
        active ? "bg-brand-soft font-semibold text-ink" : "font-medium text-nav"
      }`}
    >
      {icon}
      {children}
    </div>
  );
}

function MockStat({
  label,
  value,
  delta,
  deltaClass,
  icon,
}: {
  label: string;
  value: string;
  delta: string;
  deltaClass: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-hairline bg-surface px-[14px] py-[13px]">
      <div className="flex items-start justify-between">
        <span className="text-[11px] text-subtext">{label}</span>
        {icon}
      </div>
      <div className="mt-[5px] text-[22px] font-bold">{value}</div>
      <div className={`mt-[2px] text-[10.5px] ${deltaClass}`}>{delta}</div>
    </div>
  );
}

const STATUS_PILL = {
  completed: { cls: "text-success bg-success-soft", label: "Completed", icon: <CheckCircle weight="fill" size={11} /> },
  processing: { cls: "text-warning bg-warning-soft", label: "Processing", icon: <CircleNotch size={11} /> },
  review: { cls: "text-review bg-review-soft", label: "Needs Review", icon: <Flag weight="fill" size={11} /> },
} as const;

function MockRow({
  title,
  status,
  last,
}: {
  title: string;
  status: keyof typeof STATUS_PILL;
  last?: boolean;
}) {
  const pill = STATUS_PILL[status];
  return (
    <div
      className={`flex items-center justify-between gap-[10px] px-4 py-[10px] ${
        last ? "" : "border-b border-[#f4f4f6]"
      }`}
    >
      <div className="min-w-0">
        <div className="text-[12.5px] font-semibold">{title}</div>
        <div className="mt-[2px] flex items-center gap-[5px] text-[10.5px] text-mute">
          <img src={asset("datadog-mark.png")} alt="" className="size-[13px] rounded-[3px]" />
          Datadog
          <ArrowRight weight="bold" size={9} className="text-[#b7b7c0]" />
          <img src={asset("airbnb-mark.png")} alt="" className="size-[13px] rounded-[3px]" />
          Airbnb
        </div>
      </div>
      <span className={`inline-flex flex-none items-center gap-1 rounded-full px-[9px] py-[3px] text-[10.5px] font-semibold ${pill.cls}`}>
        {pill.icon}
        {pill.label}
      </span>
    </div>
  );
}

function QuickStep({
  bg,
  icon,
  title,
  sub,
}: {
  bg: string;
  icon: ReactNode;
  title: string;
  sub: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className={`flex size-[22px] flex-none items-center justify-center rounded-md ${bg}`}>
        {icon}
      </span>
      <div>
        <div className="text-[11.5px] font-semibold">{title}</div>
        <div className="text-[9.5px] text-mute">{sub}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------ Value statement --- */

function ValueStatement() {
  return (
    <section className="border-t border-hairline bg-page px-6 py-[120px] text-center">
      <p className="mx-auto max-w-[780px] text-[clamp(26px,3.6vw,40px)] font-bold leading-[1.25] tracking-[-0.03em] text-balance">
        It doesn&rsquo;t just know your company. It knows who you&rsquo;re
        pitching.{" "}
        <span className="text-mute">
          Every material is grounded in two sets of documents — the
          sender&rsquo;s and the receiver&rsquo;s.
        </span>
      </p>
    </section>
  );
}

/* --------------------------------------------------------- How it works --- */

function HowItWorks() {
  return (
    <section id="how" className="pt-[110px]">
      <div className="px-6 text-center">
        <div className="text-[13px] font-semibold uppercase tracking-[.12em] text-brand">
          How it works
        </div>
        <h2 className="mx-auto mt-[14px] max-w-[640px] text-[clamp(34px,4.6vw,52px)] font-extrabold leading-[1.06] tracking-[-0.04em] text-balance">
          From PDFs to publish-ready. Four steps.
        </h2>
      </div>

      <Phase
        n="01"
        title="Create both companies"
        body="Profile the sender — you — and the receiver you're pitching. A name and an industry is enough to start; the documents fill in the rest."
        tint="from-[#eef0fe] to-[#f4f4fd]"
      >
        <PhaseCreate />
      </Phase>

      <Phase
        n="02"
        title="Upload the documents"
        body="Drop PDFs into either company — profiles, case studies, reports. Text, tables, and images are extracted automatically and become the grounding for everything generated."
        tint="from-[#fdf0dd] to-[#fbf6ec]"
      >
        <PhaseUpload />
      </Phase>

      <Phase
        n="03"
        title="Create a material"
        body="Pair a sender with a receiver, pick a template, and describe the campaign goal in a sentence. Generation draws on both companies' documents."
        tint="from-[#f1eafe] to-[#f8f4fe]"
      >
        <PhaseGenerate />
      </Phase>

      <Phase
        n="04"
        title="Review and approve"
        body="The finished material, side by side with its receipts — grounding sources from both companies, word-limit meters, schema checks. Approve it, send it, or regenerate."
        tint="from-[#e7f6ed] to-[#f2faf5]"
      >
        <PhaseReview />
      </Phase>
    </section>
  );
}

function Phase({
  n,
  title,
  body,
  tint,
  children,
}: {
  n: string;
  title: string;
  body: string;
  tint: string;
  children: ReactNode;
}) {
  return (
    <div className="px-6 pt-24">
      <div className="mx-auto max-w-[1024px]">
        <div className="flex max-w-[640px] items-baseline gap-[18px]">
          <span className="font-mono text-sm font-medium tracking-[.06em] text-brand">
            {n}
          </span>
          <div>
            <h3 className="text-[clamp(26px,3.2vw,36px)] font-bold leading-[1.12] tracking-[-0.03em]">
              {title}
            </h3>
            <p className="mt-[14px] text-[17px] leading-[1.55] text-[#55555e] text-pretty">
              {body}
            </p>
          </div>
        </div>
        <div className={`mt-10 rounded-[18px] bg-gradient-to-br p-[clamp(24px,4vw,56px)] ${tint}`}>
          {children}
        </div>
      </div>
    </div>
  );
}

const MOCK_CARD =
  "rounded-[14px] border border-black/[.06] bg-surface shadow-[0_24px_70px_-24px_rgba(30,30,80,.35)]";

function PhaseCreate() {
  return (
    <div className="relative mx-auto max-w-[560px]">
      <div className={`${MOCK_CARD} p-[22px]`}>
        <div className="mb-[6px] text-[11px] font-semibold text-subtext">
          Company logo
        </div>
        <div className="flex items-center gap-[14px] rounded-[11px] border border-field bg-subtle px-[14px] py-[13px]">
          <img src={asset("datadog-logo.png")} alt="Datadog logo" className="h-7 w-auto" />
          <div className="ml-auto flex items-center gap-[9px]">
            <span className="inline-flex items-center gap-[5px] rounded-full bg-success-soft px-[9px] py-[3px] text-[11px] font-semibold text-success">
              <CheckCircle weight="fill" size={12} />
              datadog-logo.svg
            </span>
            <span className="rounded-lg border border-[#e6e6ea] bg-surface px-[10px] py-[5px] text-[11.5px] font-semibold text-[#55555e]">
              Replace
            </span>
          </div>
        </div>
        <div className="mt-[18px] grid grid-cols-2 gap-3">
          <MockField label="Company name" value="Datadog" />
          <MockField label="Website" value="datadoghq.com" />
          <MockField label="Industry" value="Cloud Monitoring" />
          <MockField label="Tone of voice" value="Professional" />
        </div>
        <div className="mt-[14px] flex items-start gap-2 rounded-[10px] border border-[#e6e6fb] bg-[#f4f4fd] px-3 py-[10px]">
          <Sparkle weight="fill" size={15} className="mt-[1px] flex-none text-brand" />
          <span className="text-xs leading-[1.5] text-body">
            Leave the rest blank — after documents upload, the profile fills
            itself in.
          </span>
        </div>
        <div className="mt-4 flex justify-end">
          <span className="inline-flex items-center gap-[6px] rounded-[9px] bg-brand px-[14px] py-[9px] text-[12.5px] font-semibold text-white">
            Create &amp; upload documents
            <ArrowRight weight="bold" size={13} />
          </span>
        </div>
      </div>
      {/* Floating receiver chip */}
      <div className="absolute -right-[14px] -top-[22px] flex items-center gap-[10px] rounded-xl border border-black/[.06] bg-surface px-[14px] py-[11px] shadow-[0_16px_44px_-16px_rgba(30,30,80,.35)]">
        <div>
          <img src={asset("airbnb-logo.png")} alt="Airbnb logo" className="block h-[21px] w-auto" />
          <div className="mt-[5px] text-[10.5px] text-mute">
            Travel Marketplace · Receiver
          </div>
        </div>
      </div>
    </div>
  );
}

function MockField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-[5px] text-[11px] font-semibold text-subtext">
        {label}
      </div>
      <div className="rounded-[9px] border border-field bg-subtle px-[11px] py-[9px] text-[13px] text-[#2f2f38]">
        {value}
      </div>
    </div>
  );
}

function PhaseUpload() {
  return (
    <div className={`mx-auto max-w-[620px] ${MOCK_CARD} p-5`}>
      <div className="flex items-center gap-[10px]">
        <img src={asset("datadog-mark.png")} alt="Datadog logo" className="size-[30px] flex-none rounded-[7px]" />
        <span className="text-sm font-bold">Datadog</span>
        <span className="ml-auto font-mono text-[11px] text-mute">
          3 documents
        </span>
      </div>
      <div className="mt-[14px] flex flex-col items-center gap-[6px] rounded-[11px] border border-dashed border-[#cfcfe4] bg-[#fafafe] p-[18px]">
        <div className="flex size-[34px] items-center justify-center rounded-[9px] bg-brand-soft">
          <UploadSimple size={18} className="text-brand" />
        </div>
        <div className="text-[13px] font-semibold">
          Drop PDFs here or <span className="text-brand">browse</span>
        </div>
        <div className="text-[11.5px] text-mute">
          Text, tables and images extracted automatically
        </div>
      </div>
      <div className="mt-[14px] overflow-hidden rounded-[11px] border border-[#f0f0f2]">
        <DocRow name="platform-overview.pdf" meta="24 pages · 96 chunks · 6 tables · 12 images" status="processed" />
        <DocRow name="apm-case-study.pdf" meta="8 pages · 31 chunks · 2 tables · 4 images" status="processed" divided />
        <DocRow name="security-compliance.pdf" meta="31 pages · extracting…" status="processing" divided />
      </div>
    </div>
  );
}

function DocRow({
  name,
  meta,
  status,
  divided,
}: {
  name: string;
  meta: string;
  status: "processed" | "processing";
  divided?: boolean;
}) {
  return (
    <div className={`flex items-center gap-[10px] px-[13px] py-[11px] ${divided ? "border-t border-[#f4f4f6]" : ""}`}>
      <FilePdf weight="fill" size={19} className="text-[#dc4b3e]" />
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-semibold">{name}</div>
        <div className="mt-[1px] text-[11px] text-mute">{meta}</div>
      </div>
      {status === "processed" ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-[3px] text-[10.5px] font-semibold text-success">
          <CheckCircle weight="fill" size={11} />
          Processed
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-[3px] text-[10.5px] font-semibold text-warning">
          <CircleNotch size={11} />
          Processing
        </span>
      )}
    </div>
  );
}

function PhaseGenerate() {
  return (
    <div className={`mx-auto max-w-[660px] ${MOCK_CARD} p-[22px]`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold">New marketing material</span>
        <span className="font-mono text-[11px] text-mute">step 3 / 4</span>
      </div>
      <div className="mt-[14px] grid grid-cols-[1fr_36px_1fr] items-stretch gap-[10px]">
        <PairCard label="Sender" logo="datadog-mark.png" name="Datadog" sub="Cloud Monitoring · 3 docs" />
        <div className="flex size-[30px] items-center justify-center justify-self-center self-center rounded-full bg-brand-soft">
          <ArrowsLeftRight weight="bold" size={14} className="text-brand" />
        </div>
        <PairCard label="Receiver" logo="airbnb-mark.png" name="Airbnb" sub="Travel Marketplace · 5 docs" />
      </div>
      <div className="mt-3 rounded-[10px] bg-rail px-3 py-[10px] text-xs leading-[1.5] text-body">
        <b className="font-bold">Datadog</b> is pitching to{" "}
        <b className="font-bold">Airbnb</b> — grounding draws from both
        companies&rsquo; documents.
      </div>
      <div className="mt-3">
        <div className="mb-[5px] text-[11px] font-semibold text-subtext">
          Campaign goal
        </div>
        <div className="rounded-[10px] border border-field bg-subtle px-3 py-[11px] text-[12.5px] italic leading-[1.5] text-body">
          &ldquo;A short article on how Datadog could keep Airbnb&rsquo;s booking
          flow reliable during peak travel season.&rdquo;
        </div>
      </div>
      <div className="mt-[14px] flex items-center justify-center gap-[7px] rounded-[10px] bg-brand p-[11px] text-[13px] font-semibold text-white">
        <MagicWand weight="fill" size={15} />
        Generate Marketing Material
      </div>
    </div>
  );
}

function PairCard({
  label,
  logo,
  name,
  sub,
}: {
  label: string;
  logo: string;
  name: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl border border-hairline p-3">
      <div className="mb-[9px] flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[.07em] text-faint">
          {label}
        </span>
        <CheckCircle weight="fill" size={15} className="text-brand" />
      </div>
      <div className="flex items-center gap-[9px]">
        <img src={asset(logo)} alt={`${name} logo`} className="size-8 flex-none rounded-lg" />
        <div>
          <div className="text-[13px] font-bold">{name}</div>
          <div className="text-[11px] text-mute">{sub}</div>
        </div>
      </div>
    </div>
  );
}

function PhaseReview() {
  return (
    <div className="mx-auto grid max-w-[880px] grid-cols-1 items-start gap-4 md:grid-cols-[1.15fr_.85fr]">
      {/* Preview card */}
      <div className={`overflow-hidden ${MOCK_CARD}`}>
        <div className="relative h-[180px] bg-[radial-gradient(90%_130%_at_85%_0%,rgba(177,98,255,.55),transparent_60%),radial-gradient(80%_120%_at_10%_100%,rgba(255,90,95,.35),transparent_55%),linear-gradient(120deg,#251243,#632ca6)]">
          <div className="absolute bottom-3 left-3 flex items-center gap-[6px] rounded-lg bg-surface px-[9px] py-[5px] shadow-[0_2px_8px_rgba(0,0,0,.15)]">
            <img src={asset("datadog-mark.png")} alt="Datadog logo" className="size-4 rounded" />
            <span className="text-[10.5px] font-bold text-ink">Datadog</span>
          </div>
        </div>
        <div className="px-5 py-[18px]">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[.08em] text-brand">
            Datadog × Airbnb
          </div>
          <div className="text-[17px] font-bold leading-[1.25] tracking-[-0.02em]">
            Reliability for Every Booking
          </div>
          <p className="my-[7px] mb-3 text-xs leading-[1.5] text-[#55555e]">
            How unified observability could help Airbnb catch issues before
            guests ever notice.
          </p>
          <div className="mb-[3px] text-xs font-bold">The Challenge</div>
          <p className="mb-[10px] text-[11.5px] leading-[1.55] text-body">
            Peak travel weekends amplify every regression across Airbnb&rsquo;s
            thousands of microservices — booking, payments, messaging.
          </p>
          <div className="mb-[3px] text-xs font-bold">The Solution</div>
          <p className="mb-3 text-[11.5px] leading-[1.55] text-body">
            Datadog would correlate Airbnb&rsquo;s metrics, traces and logs in
            one view — cutting time-to-root-cause from hours to minutes.
          </p>
          <div className="flex items-center gap-[7px] rounded-[9px] border border-[#e6e6fb] bg-[#f4f4fd] px-[11px] py-[9px]">
            <CalendarCheck weight="fill" size={14} className="text-brand" />
            <span className="text-[11.5px] font-semibold text-[#3a3a42]">
              Book a 20-minute observability review
            </span>
          </div>
        </div>
      </div>
      {/* Right rail */}
      <div className="flex flex-col gap-3">
        <RailCard title="Quality checks">
          <div className="flex flex-col gap-[7px]">
            {["JSON schema valid", "Word limits passed", "Image slots present", "Sources attached"].map((c) => (
              <div key={c} className="flex items-center gap-[7px]">
                <CheckCircle weight="fill" size={15} className="text-success" />
                <span className="text-[12.5px] text-[#2f2f38]">{c}</span>
              </div>
            ))}
          </div>
        </RailCard>
        <RailCard title="Constraint meters">
          <Meter label="Headline" used="5 / 10" pct={50} />
          <Meter label="Subheadline" used="13 / 22" pct={59} />
          <Meter label="Body · Challenge" used="54 / 80" pct={68} warn />
          <Meter label="Body · Solution" used="61 / 80" pct={76} warn last />
        </RailCard>
        <RailCard title="Sources">
          <div className="flex flex-col gap-2">
            <SourceLine dir="sender" file="platform-overview.pdf · p.4" />
            <SourceLine dir="receiver" file="booking-architecture.pdf · p.3" />
            <SourceLine dir="receiver" file="peak-season-review.pdf · p.5" />
          </div>
        </RailCard>
      </div>
    </div>
  );
}

function RailCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-black/[.06] bg-surface px-[15px] py-[14px] shadow-[0_16px_44px_-18px_rgba(30,30,80,.3)]">
      <div className="mb-[10px] text-[10px] font-semibold uppercase tracking-[.07em] text-faint">
        {title}
      </div>
      {children}
    </div>
  );
}

function Meter({
  label,
  used,
  pct,
  warn,
  last,
}: {
  label: string;
  used: string;
  pct: number;
  warn?: boolean;
  last?: boolean;
}) {
  return (
    <>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs text-[#2f2f38]">{label}</span>
        <span className={`font-mono text-[10.5px] ${warn ? "text-warning" : "text-subtext"}`}>
          {used}
        </span>
      </div>
      <div className={`h-1 rounded ${last ? "" : "mb-[9px]"} bg-[#f0f0f2]`}>
        <div
          className={`h-1 rounded ${warn ? "bg-[#e0a83b]" : "bg-success"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </>
  );
}

function SourceLine({ dir, file }: { dir: "sender" | "receiver"; file: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`flex size-[18px] flex-none items-center justify-center rounded-[5px] ${
          dir === "sender" ? "bg-brand-soft" : "bg-[#ffecec]"
        }`}
      >
        {dir === "sender" ? (
          <ArrowUpRight weight="bold" size={10} className="text-brand" />
        ) : (
          <ArrowDownLeft weight="bold" size={10} className="text-[#e0484d]" />
        )}
      </span>
      <span className="font-mono text-[10.5px] text-body">{file}</span>
    </div>
  );
}

/* -------------------------------------------------------- Sources band --- */

function SourcesBand() {
  return (
    <section
      id="sources"
      className="mt-[140px] border-t border-hairline bg-page px-6 py-[110px]"
    >
      <div className="mx-auto grid max-w-[1024px] items-center gap-14 md:grid-cols-2">
        <div>
          <div className="text-[13px] font-semibold uppercase tracking-[.12em] text-brand">
            Sources
          </div>
          <h2 className="mt-[14px] text-[clamp(28px,3.6vw,40px)] font-extrabold leading-[1.1] tracking-[-0.035em] text-balance">
            Every claim, receipted.
          </h2>
          <p className="mt-[18px] max-w-[420px] text-[16.5px] leading-[1.6] text-[#55555e] text-pretty">
            Generation retrieves passages from both companies&rsquo; document
            libraries and pins every claim to its file and page. Reviewers open
            the PDF at the exact spot — nothing is taken on faith.
          </p>
        </div>
        <div className="w-full max-w-[440px] justify-self-center rounded-[14px] border border-hairline bg-surface p-[18px] shadow-[0_24px_70px_-24px_rgba(30,30,80,.25)]">
          <div className="flex items-center justify-between">
            <span className="text-[10.5px] font-semibold uppercase tracking-[.07em] text-faint">
              Grounding sources
            </span>
            <span className="font-mono text-[10.5px] text-mute">
              4 passages · 2 companies
            </span>
          </div>
          <SourceHeading dir="sender" label="Sender — Datadog" />
          <SourceQuote
            file="platform-overview.pdf"
            page="p.4"
            quote="Datadog unifies metrics, traces and logs in one platform — teams cut mean time to resolution from hours to minutes."
          />
          <SourceHeading dir="receiver" label="Receiver — Airbnb" />
          <SourceQuote
            file="booking-architecture.pdf"
            page="p.3"
            quote="Airbnb's platform spans thousands of services, serving millions of guests during peak weekends."
          />
        </div>
      </div>
    </section>
  );
}

function SourceHeading({ dir, label }: { dir: "sender" | "receiver"; label: string }) {
  return (
    <div className="mt-[14px] flex items-center gap-[7px]">
      <span
        className={`flex size-[18px] items-center justify-center rounded-[5px] ${
          dir === "sender" ? "bg-brand-soft" : "bg-[#ffecec]"
        }`}
      >
        {dir === "sender" ? (
          <ArrowUpRight weight="bold" size={10} className="text-brand" />
        ) : (
          <ArrowDownLeft weight="bold" size={10} className="text-[#e0484d]" />
        )}
      </span>
      <span className="text-[11.5px] font-semibold text-body">{label}</span>
    </div>
  );
}

function SourceQuote({
  file,
  page,
  quote,
}: {
  file: string;
  page: string;
  quote: string;
}) {
  return (
    <div className="mt-2 rounded-[11px] border border-[#f0f0f2] p-3">
      <div className="flex items-center gap-2">
        <FilePdf weight="fill" size={16} className="text-[#dc4b3e]" />
        <span className="text-[12.5px] font-semibold">{file}</span>
        <span className="rounded-[5px] bg-[#f4f4f6] px-[6px] py-[2px] font-mono text-[10.5px] text-subtext">
          {page}
        </span>
        <ArrowSquareOut size={13} className="ml-auto text-mute" />
      </div>
      <p className="mt-[7px] text-[11.5px] italic leading-[1.55] text-[#55555e]">
        &ldquo;{quote}&rdquo;
      </p>
    </div>
  );
}

/* ------------------------------------------------------------- Features --- */

const FEATURES = [
  {
    eyebrow: "Sender × Receiver",
    title: "Two-sided by design.",
    body: "Materials are written from both companies' context — your strengths, aimed at their reality.",
  },
  {
    eyebrow: "Grounded",
    title: "Every sentence has a source.",
    body: "Copy cites the exact document and page it came from. Open the PDF at the cited page in one click.",
  },
  {
    eyebrow: "Validated",
    title: "Constraints, enforced.",
    body: "Word limits, image slots, JSON schema — every output is checked against the template before review.",
  },
  {
    eyebrow: "Structured",
    title: "Layout JSON, not a blob.",
    body: "Output maps into a layout contract — ready to render in any channel, not just copy-paste text.",
  },
];

function Features() {
  return (
    <section id="features" className="px-6 py-[120px]">
      <div className="mx-auto max-w-[1024px]">
        <h2 className="max-w-[560px] text-[clamp(30px,4vw,44px)] font-extrabold leading-[1.08] tracking-[-0.035em] text-balance">
          Generated doesn&rsquo;t mean made up.
        </h2>
        <div className="mt-14 grid grid-cols-1 gap-[18px] sm:grid-cols-2">
          {FEATURES.map((f) => (
            <div key={f.eyebrow} className="rounded-[18px] bg-page px-[26px] py-7">
              <div className="font-mono text-[11.5px] font-medium uppercase tracking-[.08em] text-brand">
                {f.eyebrow}
              </div>
              <h3 className="mt-[14px] text-[20px] font-bold tracking-[-0.02em]">
                {f.title}
              </h3>
              <p className="mt-[10px] text-sm leading-[1.6] text-[#55555e] text-pretty">
                {f.body}
              </p>
            </div>
          ))}
          <DeliveredCard />
        </div>
      </div>
    </section>
  );
}

function DeliveredCard() {
  return (
    <div className="grid grid-cols-1 items-center gap-8 rounded-[18px] bg-ink p-[clamp(28px,4vw,44px)] sm:col-span-2 md:grid-cols-2">
      <div>
        <div className="font-mono text-[11.5px] font-medium uppercase tracking-[.08em] text-[#b9b9f2]">
          Delivered
        </div>
        <h3 className="mt-[14px] text-[clamp(22px,2.8vw,28px)] font-extrabold leading-[1.15] tracking-[-0.03em] text-white text-balance">
          Connect your domain. We send it.
        </h3>
        <p className="mt-3 max-w-[400px] text-[14.5px] leading-[1.6] text-faint text-pretty">
          Verify your sender domain once — approved materials go out as email
          from your own address, straight from the review screen.
        </p>
      </div>
      <div className="w-full max-w-[400px] justify-self-center rounded-xl bg-surface p-4 shadow-[0_24px_70px_-24px_rgba(0,0,0,.5)]">
        <div className="text-[10px] font-semibold uppercase tracking-[.07em] text-faint">
          From
        </div>
        <div className="my-1 mb-3 flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-bold text-ink">
            julie@datadoghq.com
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-[3px] text-[10.5px] font-semibold text-success">
            <CheckCircle weight="fill" size={11} />
            datadoghq.com connected
          </span>
        </div>
        <div className="text-[10px] font-semibold uppercase tracking-[.07em] text-faint">
          To
        </div>
        <div className="my-1 mb-[14px] text-[13px] text-[#2f2f38]">
          partnerships@airbnb.com
        </div>
        <div className="flex items-center justify-between gap-[10px] border-t border-[#f0f0f2] pt-3">
          <span className="font-mono text-[10.5px] text-mute">
            newsletter_article_v1
          </span>
          <span className="inline-flex items-center gap-[6px] rounded-lg bg-brand px-3 py-[7px] text-xs font-semibold text-white">
            <PaperPlaneTilt weight="fill" size={12} />
            Send email
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------ Templates band --- */

function TemplatesBand() {
  return (
    <section className="border-y border-hairline bg-page px-6 py-[110px]">
      <div className="mx-auto grid max-w-[1024px] items-center gap-14 md:grid-cols-2">
        <div>
          <div className="text-[13px] font-semibold uppercase tracking-[.12em] text-brand">
            Templates
          </div>
          <h2 className="mt-[14px] text-[clamp(28px,3.6vw,40px)] font-extrabold leading-[1.1] tracking-[-0.035em] text-balance">
            One JSON contract. Every layout.
          </h2>
          <p className="mt-[18px] max-w-[420px] text-[16.5px] leading-[1.6] text-[#55555e] text-pretty">
            Each template defines fields, word limits, and image slots. Output is
            validated against them before you ever see it — newsletter today,
            brochures and email next.
          </p>
        </div>
        <div className="w-full max-w-[420px] justify-self-center rounded-[14px] border border-hairline bg-surface p-[18px] shadow-[0_24px_70px_-24px_rgba(30,30,80,.25)]">
          <div className="flex items-center gap-[10px] border-b border-[#f0f0f2] pb-[14px]">
            <div className="flex size-8 flex-none items-center justify-center rounded-[9px] bg-brand-soft">
              <Newspaper size={16} className="text-brand" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-bold">Newsletter Article</div>
              <div className="font-mono text-[10.5px] text-mute">
                newsletter_article_v1
              </div>
            </div>
            <span className="rounded-full bg-success-soft px-[9px] py-[3px] text-[10.5px] font-semibold text-success">
              Active
            </span>
          </div>
          <ConstraintRow label="Headline" value="≤ 10 words" first />
          <ConstraintRow label="Subheadline" value="≤ 22 words" />
          <ConstraintRow label="Body sections" value="2 × ≤ 80 words" />
          <ConstraintRow label="CTA" value="≤ 15 words" />
          <div className="mt-[10px] flex gap-2">
            <span className="inline-flex items-center gap-[5px] rounded-lg border border-hairline px-[9px] py-[5px] text-[11px] text-[#55555e]">
              <ImageIcon size={12} />
              Hero · 1200×630
            </span>
            <span className="inline-flex items-center gap-[5px] rounded-lg border border-hairline px-[9px] py-[5px] text-[11px] text-[#55555e]">
              <ImageIcon size={12} />
              Logo · SVG/PNG
            </span>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Swatch color="#5b5bd6" />
            <Swatch color="#0f172a" />
          </div>
        </div>
      </div>
    </section>
  );
}

function ConstraintRow({
  label,
  value,
  first,
}: {
  label: string;
  value: string;
  first?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between ${first ? "pb-1 pt-2" : "py-1"}`}>
      <span className="text-[12.5px] text-[#2f2f38]">{label}</span>
      <span className="font-mono text-[11px] text-subtext">{value}</span>
    </div>
  );
}

function Swatch({ color }: { color: string }) {
  return (
    <span className="inline-flex items-center gap-[6px]">
      <span className="size-[18px] rounded-[5px]" style={{ background: color }} />
      <span className="font-mono text-[10.5px] text-subtext">{color}</span>
    </span>
  );
}

/* ------------------------------------------------------------ Final CTA --- */

function FinalCta() {
  return (
    <section id="cta" className="bg-ink px-6 py-[130px] text-center">
      <h2 className="mx-auto max-w-[620px] text-[clamp(36px,5vw,56px)] font-extrabold leading-[1.05] tracking-[-0.04em] text-white text-balance">
        Start generating.
      </h2>
      <p className="mx-auto mt-5 max-w-[460px] text-[17px] leading-[1.55] text-faint">
        Sign in, add both companies, drop in the PDFs. The first article takes
        minutes.
      </p>
      <div className="mt-[34px] flex flex-wrap justify-center gap-[14px]">
        <a
          href={LOGIN}
          className="rounded-full bg-brand px-[30px] py-[14px] text-[15.5px] font-semibold text-white hover:bg-brand-hover"
        >
          Get started
        </a>
        <a
          href={LOGIN}
          className="rounded-full border border-white/[.28] px-[30px] py-[14px] text-[15.5px] font-semibold text-white hover:bg-white/[.08]"
        >
          Request a demo
        </a>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------- Footer --- */

function Footer() {
  return (
    <footer className="border-t border-white/[.08] bg-ink px-6 py-[26px]">
      <div className="mx-auto flex max-w-[1024px] flex-wrap items-center justify-between gap-4 text-[12.5px] text-subtext">
        <span>© 2026 Collateral AI</span>
      </div>
    </footer>
  );
}
