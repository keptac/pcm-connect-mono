type AlumniConnectUser = {
  member_status?: string | null;
};

const alumniConnectBlockedRoles = new Set([
  "super_admin",
  "student_admin",
  "secretary",
  "program_manager",
  "finance_officer",
  "students_finance",
  "committee_member",
  "executive",
  "director",
  "alumni_admin",
  "service_recovery",
]);

export function canAccessAlumniConnect(user: AlumniConnectUser | null | undefined, roles: string[]) {
  if (roles.some((role) => alumniConnectBlockedRoles.has(role))) {
    return false;
  }
  return ["Student", "Alumni"].includes(user?.member_status || "");
}
