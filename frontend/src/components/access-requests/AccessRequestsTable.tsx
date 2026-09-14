"use client";

import { Clock, Mail, UserRound } from "lucide-react";
import type { TranslationKey } from "@/lib/i18n";
import type {
  AccessRequest,
  AccessRequestProduct,
  AccessRequestSource,
  AccessRequestStatus,
} from "@/lib/access-requests-api";

type Translate = (key: TranslationKey) => string;

interface AccessRequestsTableProps {
  requests: AccessRequest[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (request: AccessRequest) => void;
  t: Translate;
}

const PRODUCT_LABELS: Record<AccessRequestProduct, string> = {
  syncxml: "GuestHub",
  guesthub: "GuestHub",
  synergi: "Synergi",
  data_lab: "Data Lab",
};

export function productLabel(product: AccessRequestProduct): string {
  return PRODUCT_LABELS[product] ?? "No reconocido";
}

export function statusLabel(status: AccessRequestStatus, t: Translate): string {
  const labels: Record<AccessRequestStatus, TranslationKey> = {
    pending: "accessRequestsStatusPending",
    approved: "accessRequestsStatusApproved",
    rejected: "accessRequestsStatusRejected",
    cancelled: "accessRequestsStatusCancelled",
  };
  return t(labels[status]);
}

export function sourceLabel(source: AccessRequestSource, t: Translate): string {
  const labels: Partial<Record<AccessRequestSource, TranslationKey>> = {
    syncxml_landing: "accessRequestsSourceSyncXmlLanding",
    synergi_app: "accessRequestsSourceSynergiApp",
    data_lab_app: "accessRequestsSourceDataLabApp",
    nexus_manual: "accessRequestsSourceNexusManual",
    external_api: "accessRequestsSourceExternalApi",
  };
  if (source === "guesthub_app") return "GuestHub App";
  if (source === "private_estates_landing") return "Private Estates Landing";
  if (source === "private_estates_web") return "Private Estates Web";
  return labels[source] ? t(labels[source]!) : (source || "No reconocido");
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusClassName(status: AccessRequestStatus): string {
  if (status === "approved")
    return "border-emerald-400/25 bg-emerald-950/30 text-emerald-200";
  if (status === "rejected")
    return "border-rose-400/25 bg-rose-950/30 text-rose-200";
  if (status === "cancelled")
    return "border-soft-subtle bg-navy-surface/50 text-soft-muted";
  return "border-gold/25 bg-gold/10 text-gold";
}

export function AccessRequestsTable({
  requests,
  selectedId,
  loading,
  onSelect,
  t,
}: AccessRequestsTableProps) {
  if (loading) {
    return (
      <div className="surface-secondary rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-4 text-sm text-soft-muted">
        {t("accessRequestsLoading")}
      </div>
    );
  }

  if (requests.length === 0) {
    return (
      <div className="surface-secondary rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-4 text-sm text-soft-muted">
        {t("accessRequestsEmpty")}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-215 border-separate border-spacing-y-2 text-left text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-[0.16em] text-soft-muted">
            <th className="px-3 py-2 font-semibold">
              {t("accessRequestsColumnCreated")}
            </th>
            <th className="px-3 py-2 font-semibold">
              {t("accessRequestsColumnProduct")}
            </th>
            <th className="px-3 py-2 font-semibold">
              {t("accessRequestsColumnStatus")}
            </th>
            <th className="px-3 py-2 font-semibold">
              {t("accessRequestsColumnApplicant")}
            </th>
            <th className="px-3 py-2 font-semibold">
              {t("accessRequestsColumnContext")}
            </th>
            <th className="px-3 py-2 font-semibold">
              {t("accessRequestsColumnSource")}
            </th>
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => {
            const active = request.id === selectedId;
            return (
              <tr
                key={request.id}
                onClick={() => onSelect(request)}
                className={`surface-secondary surface-copy-safe cursor-pointer rounded-xl border transition ${
                  active
                    ? "bg-navy-surface/70"
                    : "bg-navy-deep/35 hover:bg-navy-surface/45"
                }`}
              >
                <td className="rounded-l-xl border-y border-l border-soft-subtle/40 px-3 py-3 text-soft-muted">
                  <span className="inline-flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    {formatDate(request.created_at)}
                  </span>
                </td>
                <td className="border-y border-soft-subtle/40 px-3 py-3 font-semibold text-soft-white">
                  {productLabel(request.product)}
                </td>
                <td className="border-y border-soft-subtle/40 px-3 py-3">
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusClassName(request.status)}`}
                  >
                    {statusLabel(request.status, t)}
                  </span>
                </td>
                <td className="border-y border-soft-subtle/40 px-3 py-3">
                  <p className="flex items-center gap-2 font-semibold text-soft-white">
                    <UserRound className="h-4 w-4 text-blue-light" />
                    {request.full_name}
                  </p>
                  <p className="mt-1 flex items-center gap-2 text-xs text-soft-muted">
                    <Mail className="h-3.5 w-3.5" />
                    {request.email}
                  </p>
                </td>
                <td className="border-y border-soft-subtle/40 px-3 py-3 text-soft-muted">
                  {request.company ||
                    request.profile_type ||
                    request.service_category ||
                    "-"}
                </td>
                <td className="rounded-r-xl border-y border-r border-soft-subtle/40 px-3 py-3 text-soft-muted">
                  {sourceLabel(request.source, t)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
