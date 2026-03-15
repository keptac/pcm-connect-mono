import { PageHeader, Panel } from "../components/ui";

type SupportVariant = "help" | "contact" | "terms" | "privacy";

const contentByVariant: Record<SupportVariant, {
  eyebrow: string;
  title: string;
  description: string;
  sections: Array<{ heading: string; body?: string; bullets?: string[] }>;
}> = {
  help: {
    eyebrow: "Support",
    title: "Help",
    description: "Quick guidance for the main areas of PCM Connect.",
    sections: [
      {
        heading: "What this system is for",
        body: "PCM Connect helps teams manage people, programs, updates, funding, broadcasts, and internal coordination across universities and campuses."
      },
      {
        heading: "Where to go",
        bullets: [
          "Overview gives the current operational picture.",
          "People and Alumni connect cover member records and graduate engagement.",
          "Programs, Calendar, Broadcasts, and Updates support ministry planning and reporting.",
          "Funding tracks cash inflow, outflow, and category comparisons.",
          "Team is for account administration and password resets."
        ]
      },
      {
        heading: "If something is blocked",
        body: "Access depends on your assigned role and scope. If a page or action is unavailable, contact support or a super admin."
      }
    ]
  },
  contact: {
    eyebrow: "Support",
    title: "Contact",
    description: "Use these support channels for account and system issues.",
    sections: [
      {
        heading: "Support contact",
        bullets: [
          "Email: kchelenje@gmail.com",
          "WhatsApp: +263785302628"
        ]
      },
      {
        heading: "When to contact support",
        bullets: [
          "Password or login problems",
          "Role and access issues",
          "Data correction requests",
          "System errors or upload failures"
        ]
      }
    ]
  },
  terms: {
    eyebrow: "Legal",
    title: "Terms and Conditions",
    description: "Simple terms for using PCM Connect.",
    sections: [
      {
        heading: "Authorized use",
        body: "Use PCM Connect only for legitimate PCM administration, reporting, communication, and operational record keeping."
      },
      {
        heading: "Account responsibility",
        body: "You are responsible for keeping your sign-in details secure and for all activity performed through your account."
      },
      {
        heading: "Data quality and conduct",
        body: "Information entered into the system should be accurate, lawful, and respectful of members, staff, alumni, donors, and partner institutions."
      },
      {
        heading: "Service changes",
        body: "PCM may update features, policies, and these terms as operational needs change. Continued use means you accept the updated terms."
      }
    ]
  },
  privacy: {
    eyebrow: "Legal",
    title: "Privacy",
    description: "This summary follows general GDPR-aligned privacy principles for global use.",
    sections: [
      {
        heading: "What data is used",
        body: "PCM Connect may process profile details, role assignments, university affiliation, contact details, ministry records, uploaded files, and operational finance data."
      },
      {
        heading: "Why data is used",
        body: "The system uses personal and operational data to manage access, run programs, maintain records, produce reports, and support legitimate ministry administration."
      },
      {
        heading: "Privacy principles",
        bullets: [
          "Use only data that is necessary for the service.",
          "Keep records accurate and reasonably up to date.",
          "Protect data with role-based access and technical safeguards.",
          "Retain data only as long as operational, legal, or safeguarding needs require."
        ]
      },
      {
        heading: "Your rights",
        body: "Where applicable, users may request access, correction, or review of personal data, subject to lawful and operational limits."
      }
    ]
  }
};

export default function SupportInfoPage({ variant }: { variant: SupportVariant }) {
  const content = contentByVariant[variant];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={content.eyebrow}
        title={content.title}
        description={content.description}
      />

      <div className="grid gap-5 lg:grid-cols-2">
        {content.sections.map((section) => (
          <Panel key={section.heading} className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-950">{section.heading}</h3>
              {section.body ? <p className="mt-2 text-sm leading-7 text-slate-600">{section.body}</p> : null}
            </div>

            {section.bullets?.length ? (
              <ul className="space-y-2 pl-5 text-sm leading-7 text-slate-600 list-disc">
                {section.bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            ) : null}
          </Panel>
        ))}
      </div>
    </div>
  );
}
