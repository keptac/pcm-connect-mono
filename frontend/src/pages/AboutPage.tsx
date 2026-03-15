import { Link } from "react-router-dom";

import heroImage from "../images/background-image-1.jpg";
import pcmLogo from "../images/pcm_logo.png";
import { APP_VERSION } from "../lib/appVersion";

const featureGroups = [
  {
    title: "People and identity",
    description: "Manage student, staff, alumni, volunteer, and partner records with scoped access across universities and campuses."
  },
  {
    title: "Programs and events",
    description: "Track ministry programs, calendar activity, broadcast invitations, and operational follow-through in one workspace."
  },
  {
    title: "Funding and treasury",
    description: "Capture cash inflow and outflow, compare categories, and monitor weekly or monthly treasury movement."
  },
  {
    title: "Reporting and PDFs",
    description: "Submit update narratives, attach evidence, and generate polished PDF reports and report packs for leadership review."
  },
  {
    title: "Messaging and coordination",
    description: "Use secure direct messaging, shared broadcasts, and role-based communication to keep teams aligned."
  },
  {
    title: "Marketplace",
    description: "Provides alumni access to show case products and services and provides a controlled space for PCM community exchange."
  }
];

const audiencePillars = [
  "Super admin oversight",
  "Campus and alumni administration",
  "Finance operations",
  "Program delivery and reporting",
  "Member self-service registration"
];

export default function AboutPage() {
  return (
    <div className="about-page min-h-screen bg-[linear-gradient(180deg,#f8fbff_0%,#eef3fa_100%)] text-slate-900">
      <div className="relative overflow-hidden border-b border-slate-200/70 bg-[linear-gradient(140deg,rgba(18,36,63,0.96),rgba(47,119,189,0.88)_46%,rgba(113,87,186,0.8))] text-white">
        <div
          className="absolute inset-0 opacity-15"
          style={{ backgroundImage: `url(${heroImage})`, backgroundSize: "cover", backgroundPosition: "center" }}
        />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.16),transparent_26%),radial-gradient(circle_at_18%_20%,rgba(255,255,255,0.14),transparent_22%)]" />

        <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-10 px-4 py-5 sm:px-8 lg:px-10 lg:py-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="grid h-16 w-16 place-items-center rounded-[16px] bg-white/8 shadow-[0_18px_34px_rgba(0,0,0,0.12)]">
                <img src={pcmLogo} alt="PCM logo" className="h-full w-full object-contain p-2.5" />
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-white/70">NZC Public Campus Ministries</p>
                <h1 className="text-2xl font-semibold tracking-[-0.03em] text-white sm:text-3xl">PCM Connect</h1>
                <p className="mt-2 text-sm text-white/72">Mission operations platform for campuses, alumni, staff, and leadership.</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-white/16 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-white/78">
                Version {APP_VERSION}
              </span>
              <Link
                to="/login"
                className="inline-flex items-center justify-center rounded-[12px] border border-white/14 bg-white px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
              >
                Sign in
              </Link>
            </div>
          </div>

          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div className="space-y-5">
              <p className="text-sm font-semibold uppercase tracking-[0.34em] text-white/70">About the system</p>
              <h2 className="max-w-4xl text-4xl font-semibold leading-tight tracking-[-0.04em] text-white sm:text-6xl">
                One platform for PCM visibility, accountability, and coordination.
              </h2>
              <p className="max-w-3xl text-base leading-8 text-white/82 sm:text-lg">
                PCM Connect brings records, treasury activity, programs, reporting, messaging, and role-based administration
                into one structured system built for real campus ministry operations.
              </p>
            </div>

            <div className="grid gap-3 rounded-[20px] border border-white/12 bg-white/10 p-5 shadow-[0_24px_54px_rgba(0,0,0,0.12)] backdrop-blur">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-white/72">Designed for</p>
              <div className="flex flex-wrap gap-2">
                {audiencePillars.map((item) => (
                  <span key={item} className="rounded-full border border-white/12 bg-white/10 px-3 py-2 text-sm text-white/86">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-7xl space-y-8 px-4 py-8 sm:px-8 lg:px-10 lg:py-10">
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {featureGroups.map((feature) => (
            <section
              key={feature.title}
              className="rounded-[20px] border border-slate-200/80 bg-white/90 p-6 shadow-[0_18px_44px_rgba(18,36,63,0.08)]"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">Feature</p>
              <h3 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-slate-950">{feature.title}</h3>
              <p className="mt-4 text-sm leading-7 text-slate-600">{feature.description}</p>
            </section>
          ))}
        </div>

        <section className="rounded-[22px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,248,253,0.94))] p-6 shadow-[0_18px_44px_rgba(18,36,63,0.08)] sm:p-8">
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">Operational scope</p>
              <h3 className="text-3xl font-semibold tracking-[-0.03em] text-slate-950">What PCM Connect covers</h3>
              <p className="text-sm leading-7 text-slate-600">
                The system is built to support real ministry operations from registration and member records to financial
                controls, update submissions, governance, and password recovery.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[18px] border border-slate-200 bg-slate-50/80 p-5">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Visibility</p>
                <p className="mt-3 text-sm leading-7 text-slate-600">University scope, member linkage, global roles, and reporting views are designed to match real PCM structures.</p>
              </div>
              <div className="rounded-[18px] border border-slate-200 bg-slate-50/80 p-5">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Governance</p>
                <p className="mt-3 text-sm leading-7 text-slate-600">Tenure tracking, forced password changes, service recovery access, and role enforcement help keep administration controlled.</p>
              </div>
              <div className="rounded-[18px] border border-slate-200 bg-slate-50/80 p-5">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Evidence</p>
                <p className="mt-3 text-sm leading-7 text-slate-600">Narratives, attachments, galleries, and exportable PDFs support structured reporting back to leadership and stakeholders.</p>
              </div>
              <div className="rounded-[18px] border border-slate-200 bg-slate-50/80 p-5">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Coordination</p>
                <p className="mt-3 text-sm leading-7 text-slate-600">Programs, events, broadcasts, and secure messaging keep planning and follow-up inside one connected workspace.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-[22px] border border-slate-200/80 bg-[linear-gradient(135deg,rgba(18,36,63,0.98),rgba(47,119,189,0.92))] p-6 text-white shadow-[0_18px_44px_rgba(18,36,63,0.12)] sm:p-8">
          <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
            <div className="space-y-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-white/70">Contact</p>
              <h3 className="text-3xl font-semibold tracking-[-0.03em] text-white">Need more information?</h3>
              <p className="text-sm leading-7 text-white/82">
                For access questions, onboarding guidance, or general PCM Connect enquiries, use the contact details below.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <a
                href="tel:+263785302628"
                className="rounded-[18px] border border-white/12 bg-white/10 p-5 transition hover:bg-white/14"
              >
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-white/70">Phone</p>
                <p className="mt-3 text-lg font-semibold text-white">+263 785 302 628</p>
              </a>
              <a
                href="mailto:kchelenje@gmail.com"
                className="rounded-[18px] border border-white/12 bg-white/10 p-5 transition hover:bg-white/14"
              >
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-white/70">Email</p>
                <p className="mt-3 text-lg font-semibold text-white">kchelenje@gmail.com</p>
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
