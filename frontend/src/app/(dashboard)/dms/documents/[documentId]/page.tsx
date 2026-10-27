"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Download,
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  Send,
  Eye,
  RotateCcw,
  Lock,
  Unlock,
} from "lucide-react";
import {
  downloadGeneratedDocument,
  listReviewDecisions,
  listGeneratedDocumentVersions,
} from "@/lib/dms-api";
import database from "@/lib/neon-data-client";

async function getAuthHeader(): Promise<string> {
  const { data: { session } } = await database.auth.getSession();
  return session?.access_token ? `Bearer ${session.access_token}` : "";
}

// Direct API calls using fetch to avoid strict SDK type constraints
async function getDocRaw(id: string): Promise<{ doc: GeneratedDocument; previewText: string | null }> {
  const authorization = await getAuthHeader();
  const res = await fetch(`/api/dms/generated-documents/${id}`, {
    headers: { "Content-Type": "application/json", Authorization: authorization },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const data = await res.json();
  const doc = data.document ?? data;
  const previewText: string | null = data.version?.canonical_text ?? null;
  return { doc, previewText };
}

async function postReviewRaw(
  id: string,
  payload: { decision: string; notes?: string; version_id?: string | null },
): Promise<void> {
  const authorization = await getAuthHeader();
  const res = await fetch(`/api/dms/generated-documents/${id}/review-decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: authorization },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `${res.status}`);
  }
}

async function postSignatureRaw(
  id: string,
  payload: { signing_level: string; signers: unknown[] },
): Promise<void> {
  const authorization = await getAuthHeader();
  const res = await fetch(`/api/dms/generated-documents/${id}/signature-flows`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: authorization },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `${res.status}`);
  }
}

// ── Types ─────────────────────────────────────────────────────────────────────

type DocStatus = "draft" | "review_required" | "approved" | "signed" | "archived";
type ValidationRisk = "low" | "medium" | "high" | "critical" | "unknown";
type ReviewDecision = "approved" | "approved_with_conditions" | "changes_required" | "rejected";

interface GeneratedDocument {
  id: string;
  title: string;
  status: DocStatus;
  folder_id: string;
  org_id: string;
  template_version_id: string;
  generated_at: string | null;
  created_at: string;
  updated_at: string;
  docx_storage_path: string | null;
  pdf_storage_path: string | null;
  variable_snapshot: Record<string, string>;
  missing_fields: string[];
  language: string;
  signing_level: string;
  current_version_id: string | null;
  download_urls?: {
    docx: string;
    pdf: string;
  };
}

interface ReviewDecisionRow {
  id: string;
  review_type: "auto" | "manual";
  status: ReviewDecision | "pending" | "escalated";
  risk_level: ValidationRisk;
  block_signing: boolean;
  reviewer_id: string | null;
  notes: string | null;
  decided_at: string | null;
  created_at: string;
}

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<DocStatus, string> = {
  draft: "Borrador",
  review_required: "Pendiente revisión",
  approved: "Aprobado",
  signed: "Firmado",
  archived: "Archivado",
};

const STATUS_COLOR: Record<DocStatus, string> = {
  draft: "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
  review_required: "text-orange-400 bg-orange-400/10 border-orange-400/30",
  approved: "text-green-400 bg-green-400/10 border-green-400/30",
  signed: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  archived: "text-gray-400 bg-gray-400/10 border-gray-400/30",
};

const RISK_COLOR: Record<ValidationRisk, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  critical: "text-red-400",
  unknown: "text-gray-400",
};

function StatusBadge({ status }: { status: DocStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${STATUS_COLOR[status]}`}>
      {status === "signed" && <Lock className="h-3 w-3" />}
      {status === "approved" && <CheckCircle className="h-3 w-3" />}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DocumentViewerPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.documentId as string;

  const [doc, setDoc] = useState<GeneratedDocument | null>(null);
  const [reviews, setReviews] = useState<ReviewDecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [sendingToSign, setSendingToSign] = useState(false);
  const [activeTab, setActiveTab] = useState<"preview" | "reviews" | "versions" | "audit">("preview");
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [versions, setVersions] = useState<unknown[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [{ doc: docData, previewText: docPreview }, reviewData] = await Promise.all([
        getDocRaw(documentId),
        listReviewDecisions(documentId).catch(() => []),
      ]);
      setDoc(docData);
      setPreviewText(docPreview);
      setReviews(reviewData as ReviewDecisionRow[]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (activeTab === "versions" && versions.length === 0) {
      listGeneratedDocumentVersions(documentId)
        .then(setVersions)
        .catch(() => setVersions([]));
    }
  }, [activeTab, documentId, versions.length]);

  const handleDownload = async (format: "docx" | "pdf") => {
    try {
      const blob = await downloadGeneratedDocument(documentId, format);
      const url = URL.createObjectURL(blob as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${doc?.title ?? documentId}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Error al descargar el documento");
    }
  };

  const handleReview = async (decision: ReviewDecision) => {
    if (!doc) return;
    setSubmittingReview(true);
    try {
      await postReviewRaw(documentId, {
        decision,
        notes: reviewNotes,
        version_id: doc.current_version_id,
      });
      setReviewNotes("");
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Error: ${msg}`);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleSendToSign = async () => {
    if (!doc) return;
    setSendingToSign(true);
    try {
      await postSignatureRaw(documentId, {
        signing_level: doc.signing_level || "simple",
        signers: [],
      });
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Error: ${msg}`);
    } finally {
      setSendingToSign(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gold-light border-t-transparent" />
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <XCircle className="h-10 w-10 text-red-400" />
        <p className="text-soft-muted">{error ?? "Documento no encontrado"}</p>
        <button onClick={() => router.back()} className="btn-secondary text-sm">
          Volver
        </button>
      </div>
    );
  }

  const isImmutable = doc.status === "signed";
  const canApprove = doc.status === "draft" || doc.status === "review_required";
  const canSendToSign = doc.status === "approved";
  const latestReview = reviews[0] ?? null;
  const blocksSigning = latestReview?.block_signing ?? false;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ── Header ── */}
      <div className="shrink-0 border-b border-border-subtle px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={() => router.back()}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border-subtle text-soft-muted transition hover:border-blue-light/40 hover:text-soft-white"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <FileText className="h-5 w-5 shrink-0 text-gold-light" />
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold text-soft-white">{doc.title}</h1>
              <p className="text-xs text-soft-muted">
                {doc.language?.toUpperCase()} · ID {doc.id.slice(0, 8)}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StatusBadge status={doc.status} />
            {isImmutable && (
              <span className="flex items-center gap-1 text-xs text-blue-400">
                <Lock className="h-3 w-3" /> Inmutable
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Toolbar ── */}
      <div className="shrink-0 flex items-center gap-2 border-b border-border-subtle bg-surface-elevated px-6 py-2">
        <button
          onClick={() => handleDownload("pdf")}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-soft-muted transition hover:bg-surface-hover hover:text-soft-white"
        >
          <Download className="h-3.5 w-3.5" /> PDF
        </button>
        <button
          onClick={() => handleDownload("docx")}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-soft-muted transition hover:bg-surface-hover hover:text-soft-white"
        >
          <Download className="h-3.5 w-3.5" /> DOCX
        </button>
        <div className="ml-auto flex items-center gap-2">
          {canApprove && !isImmutable && (
            <button
              onClick={() => handleReview("approved")}
              disabled={submittingReview}
              className="flex items-center gap-1.5 rounded-lg bg-green-600/20 px-3 py-1.5 text-xs text-green-400 transition hover:bg-green-600/30 disabled:opacity-50"
            >
              <CheckCircle className="h-3.5 w-3.5" /> Aprobar
            </button>
          )}
          {canSendToSign && !blocksSigning && (
            <button
              onClick={handleSendToSign}
              disabled={sendingToSign}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600/20 px-3 py-1.5 text-xs text-blue-400 transition hover:bg-blue-600/30 disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" /> Enviar a firma
            </button>
          )}
          {blocksSigning && (
            <span className="flex items-center gap-1.5 rounded-lg bg-red-600/10 px-3 py-1.5 text-xs text-red-400">
              <Shield className="h-3.5 w-3.5" /> Firma bloqueada
            </span>
          )}
        </div>
      </div>

      {/* ── Missing fields banner ── */}
      {doc.missing_fields && doc.missing_fields.length > 0 && (
        <div className="shrink-0 flex items-start gap-2 border-b border-yellow-400/20 bg-yellow-400/5 px-6 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-400" />
          <div className="min-w-0 text-xs text-yellow-300">
            <span className="font-medium">Campos pendientes:</span>{" "}
            {doc.missing_fields.slice(0, 6).join(", ")}
            {doc.missing_fields.length > 6 && ` +${doc.missing_fields.length - 6} más`}
          </div>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="shrink-0 flex gap-1 border-b border-border-subtle px-6">
        {(["preview", "reviews", "versions", "audit"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`border-b-2 px-4 py-2.5 text-xs font-medium transition ${
              activeTab === tab
                ? "border-gold-light text-gold-light"
                : "border-transparent text-soft-muted hover:text-soft-white"
            }`}
          >
            {tab === "preview" && "Vista previa"}
            {tab === "reviews" && `Revisiones (${reviews.length})`}
            {tab === "versions" && "Versiones"}
            {tab === "audit" && "Auditoría"}
          </button>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "preview" && (
          <div className="mx-auto max-w-3xl">
            {previewText ? (
              <article className="prose prose-invert prose-sm max-w-none rounded-xl border border-border-subtle bg-white/[0.03] px-8 py-10
                prose-headings:font-serif prose-headings:text-soft-white prose-headings:tracking-tight
                prose-h1:text-xl prose-h1:text-center prose-h1:mb-2
                prose-h2:text-sm prose-h2:uppercase prose-h2:tracking-widest prose-h2:text-gold-light prose-h2:border-b prose-h2:border-gold-light/20 prose-h2:pb-2
                prose-h3:text-xs prose-h3:text-soft-white
                prose-p:text-soft-muted prose-p:leading-relaxed
                prose-strong:text-soft-white
                prose-table:text-xs prose-thead:bg-navy-deep prose-th:text-gold-light prose-th:uppercase prose-th:tracking-wider prose-th:py-2 prose-th:px-3
                prose-td:py-1.5 prose-td:px-3 prose-td:text-soft-muted prose-td:border-b prose-td:border-border-subtle
                prose-hr:border-gold-light/30
                prose-li:text-soft-muted prose-ul:text-soft-muted">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    img: () => null,
                  }}
                >
                  {previewText}
                </ReactMarkdown>
              </article>
            ) : (
              <div className="flex flex-col items-center gap-4 py-16 text-center text-soft-muted">
                <Eye className="h-10 w-10 opacity-30" />
                <p className="text-sm">Vista previa no disponible.</p>
                <p className="text-xs opacity-60">Descarga el PDF para visualizar el documento.</p>
                <button
                  onClick={() => handleDownload("pdf")}
                  className="flex items-center gap-1.5 rounded-lg border border-border-subtle px-4 py-2 text-xs text-soft-muted transition hover:border-blue-light/40 hover:text-soft-white"
                >
                  <Download className="h-3.5 w-3.5" /> Descargar PDF
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === "reviews" && (
          <div className="mx-auto max-w-2xl space-y-4">
            {/* Review form */}
            {canApprove && !isImmutable && (
              <div className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
                <h3 className="mb-3 text-xs font-semibold text-soft-white">Añadir revisión</h3>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Notas o condiciones (opcional)..."
                  className="mb-3 w-full rounded-lg border border-border-subtle bg-surface-base px-3 py-2 text-xs text-soft-white placeholder:text-soft-subtle focus:border-blue-light/50 focus:outline-none"
                  rows={3}
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleReview("approved")}
                    disabled={submittingReview}
                    className="flex items-center gap-1.5 rounded-lg bg-green-600/20 px-3 py-1.5 text-xs text-green-400 hover:bg-green-600/30 disabled:opacity-50"
                  >
                    <CheckCircle className="h-3.5 w-3.5" /> Aprobar
                  </button>
                  <button
                    onClick={() => handleReview("approved_with_conditions")}
                    disabled={submittingReview}
                    className="flex items-center gap-1.5 rounded-lg bg-yellow-600/20 px-3 py-1.5 text-xs text-yellow-400 hover:bg-yellow-600/30 disabled:opacity-50"
                  >
                    <AlertTriangle className="h-3.5 w-3.5" /> Aprobar con condiciones
                  </button>
                  <button
                    onClick={() => handleReview("changes_required")}
                    disabled={submittingReview}
                    className="flex items-center gap-1.5 rounded-lg bg-orange-600/20 px-3 py-1.5 text-xs text-orange-400 hover:bg-orange-600/30 disabled:opacity-50"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Solicitar cambios
                  </button>
                  <button
                    onClick={() => handleReview("rejected")}
                    disabled={submittingReview}
                    className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-3 py-1.5 text-xs text-red-400 hover:bg-red-600/30 disabled:opacity-50"
                  >
                    <XCircle className="h-3.5 w-3.5" /> Rechazar
                  </button>
                </div>
              </div>
            )}

            {/* Review history */}
            {reviews.length === 0 ? (
              <p className="text-center text-xs text-soft-muted py-8">Sin revisiones</p>
            ) : (
              reviews.map((review) => (
                <div
                  key={review.id}
                  className="rounded-xl border border-border-subtle bg-surface-elevated p-4"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${
                        review.status === "approved" ? "text-green-400"
                          : review.status === "rejected" ? "text-red-400"
                          : "text-yellow-400"
                      }`}>
                        {review.status}
                      </span>
                      {review.block_signing && (
                        <span className="text-xs text-red-400 flex items-center gap-0.5">
                          <Shield className="h-3 w-3" /> bloquea firma
                        </span>
                      )}
                    </div>
                    <span className={`text-xs ${RISK_COLOR[review.risk_level]}`}>
                      {review.risk_level}
                    </span>
                  </div>
                  {review.notes && (
                    <p className="text-xs text-soft-muted">{review.notes}</p>
                  )}
                  <p className="mt-2 text-xs text-soft-subtle">
                    {review.decided_at
                      ? new Date(review.decided_at).toLocaleString("es-ES")
                      : new Date(review.created_at).toLocaleString("es-ES")}
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "versions" && (
          <div className="mx-auto max-w-2xl space-y-3">
            {(versions as Array<Record<string, unknown>>).map((v) => (
              <div
                key={v.id as string}
                className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface-elevated px-4 py-3"
              >
                <div>
                  <p className="text-xs font-medium text-soft-white">
                    v{Number(v.version_number)}
                    {Boolean(v.immutable) && (
                      <span className="ml-2 text-blue-400">
                        <Lock className="inline h-3 w-3" /> inmutable
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-soft-muted">
                    {String(v.change_summary ?? "Sin descripción")}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {Boolean(v.immutable) ? (
                    <Lock className="h-4 w-4 text-blue-400" />
                  ) : (
                    <Unlock className="h-4 w-4 text-soft-subtle" />
                  )}
                  <span className="text-xs text-soft-subtle">
                    {v.created_at ? new Date(v.created_at as string).toLocaleDateString("es-ES") : ""}
                  </span>
                </div>
              </div>
            ))}
            {versions.length === 0 && (
              <p className="text-center text-xs text-soft-muted py-8">Sin versiones</p>
            )}
          </div>
        )}

        {activeTab === "audit" && (
          <div className="mx-auto max-w-2xl">
            <div className="rounded-xl border border-border-subtle bg-surface-elevated p-6 text-center">
              <Clock className="mx-auto mb-3 h-8 w-8 text-soft-subtle" />
              <p className="text-xs text-soft-muted">
                Auditoría completa disponible en el panel de administración.
              </p>
              <p className="mt-2 text-xs text-soft-subtle">
                Documento ID: <code className="font-mono">{doc.id}</code>
              </p>
            </div>
            {/* Variable snapshot */}
            {doc.variable_snapshot && Object.keys(doc.variable_snapshot).length > 0 && (
              <div className="mt-4 rounded-xl border border-border-subtle bg-surface-elevated p-4">
                <h3 className="mb-3 text-xs font-semibold text-soft-white">
                  Snapshot de variables ({Object.keys(doc.variable_snapshot).length})
                </h3>
                <div className="max-h-64 overflow-y-auto space-y-1">
                  {Object.entries(doc.variable_snapshot).map(([k, v]) => (
                    <div key={k} className="flex gap-2 text-xs">
                      <span className="w-48 shrink-0 font-mono text-soft-subtle">{k}</span>
                      <span className="text-soft-muted truncate">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
