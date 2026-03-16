import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api/endpoints";
import { EmptyState, PageHeader, Panel, StatusBadge, TablePagination, TableSearchField, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatDate } from "../lib/format";
import { matchesTableSearch } from "../lib/tableSearch";
import { useAuthStore } from "../store/auth";

function formatActorLabel(log: any) {
  if (!log.actor_user_id) return { primary: "System", secondary: "" };
  return {
    primary: log.actor_name || `User #${log.actor_user_id}`,
    secondary: log.actor_number ? `#${log.actor_number}` : `#${log.actor_user_id}`
  };
}

export default function AuditLogsPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.roles?.includes("super_admin");
  const [search, setSearch] = useState("");
  const { data } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: adminApi.auditLogs,
    enabled: isAdmin
  });
  const filteredLogs = useMemo(() => {
    return (data || []).filter((log: any) => matchesTableSearch(search, [
      log.id,
      log.action,
      log.entity,
      log.entity_id,
      formatActorLabel(log).primary,
      formatActorLabel(log).secondary,
      formatDate(log.created_at),
      log.meta
    ]));
  }, [data, search]);
  const auditPagination = usePagination(filteredLogs);

  if (!isAdmin) {
    return <Panel><p className="text-sm text-slate-600">Admin access required.</p></Panel>;
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Audit trail"
        title="System activity log"
        description="Review who changed what, when it happened, and which records were touched."
      />

      <Panel className="space-y-5">
        <div className="flex justify-end">
          <TableSearchField
            value={search}
            onChange={setSearch}
            placeholder="Search action, actor, entity, or metadata"
          />
        </div>

        {!filteredLogs.length ? (
          <EmptyState
            title={data?.length ? "No audit entries match this search" : "No audit log entries"}
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Action</th>
                    <th>Actor</th>
                    <th>Entity ID</th>
                    <th>Date</th>
                    <th>Meta</th>
                  </tr>
                </thead>
                <tbody>
                  {auditPagination.pageItems.map((log: any) => (
                    <tr key={log.id}>
                      <td>#{log.id}</td>
                      <td>
                        <div className="table-primary">{log.action}</div>
                        <div className="table-secondary">{log.entity}</div>
                      </td>
                      <td>
                        <div className="table-primary">{formatActorLabel(log).primary}</div>
                        <div className="table-secondary">{formatActorLabel(log).secondary || "System"}</div>
                      </td>
                      <td>
                        <StatusBadge label={log.entity_id || "no entity"} tone="info" />
                      </td>
                      <td>{formatDate(log.created_at)}</td>
                      <td>
                        <div className="max-w-[360px] whitespace-pre-wrap break-words text-xs text-slate-600">
                          {JSON.stringify(log.meta || {}, null, 2)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={auditPagination}
              itemLabel="entries"
              onExport={() => exportRowsAsCsv("system-activity-log", filteredLogs.map((log: any) => ({
                id: log.id,
                action: log.action,
                entity: log.entity,
                actor: formatActorLabel(log).primary,
                actor_number: formatActorLabel(log).secondary || "",
                entity_id: log.entity_id || "",
                date: formatDate(log.created_at),
                meta: JSON.stringify(log.meta || {})
              })))}
            />
          </>
        )}
      </Panel>
    </div>
  );
}
