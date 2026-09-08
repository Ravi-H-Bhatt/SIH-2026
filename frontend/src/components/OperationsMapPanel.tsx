"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

import { dashboardApi } from "@/lib/api";
import type { OperationsMapData } from "@/types";
import { Button } from "@/components/ui/Button";

/**
 * Drop-in operations map panel: fetches /api/v1/dashboard/map and renders it.
 *
 * Leaflet touches `window` at module scope, so the map itself must be excluded
 * from SSR. Importing it dynamically here means every consumer gets that for
 * free and cannot accidentally break the server build.
 */
const OperationsMap = dynamic(() => import("@/components/OperationsMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] items-center justify-center rounded-xl border border-white/10 bg-[#111118]">
      <span className="text-sm text-slate-500">Loading map…</span>
    </div>
  ),
});

export interface OperationsMapPanelProps {
  title?: string;
  subtitle?: string;
  height?: number;
  /** Cap on scans fetched; the backend clamps this to 1000. */
  limit?: number;
  className?: string;
}

export default function OperationsMapPanel({
  title = "Operations Map",
  subtitle,
  height = 420,
  limit = 200,
  className,
}: OperationsMapPanelProps) {
  const router = useRouter();
  const [data, setData] = React.useState<OperationsMapData | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await dashboardApi.getOperationsMap(limit));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load map data");
    } finally {
      setLoading(false);
    }
  }, [limit]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const flagged = React.useMemo(
    () => (data?.points ?? []).filter((p) => p.is_criminal || p.is_wanted).length,
    [data]
  );

  return (
    <div className={className}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
          <p className="mt-0.5 text-[0.8125rem] text-slate-400">
            {subtitle ??
              (data
                ? `${data.total_points} scan origin${data.total_points === 1 ? "" : "s"} · ${
                    data.checkpoints.length
                  } checkpoint${data.checkpoints.length === 1 ? "" : "s"}`
                : "Geospatial view of recent screenings")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {flagged > 0 && (
            <span className="rounded-full border border-red-500/25 bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-400">
              {flagged} flagged
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={load} isLoading={loading}>
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <div
          role="alert"
          className="flex h-[220px] flex-col items-center justify-center gap-3 rounded-xl border border-red-500/20 bg-red-500/[0.06] px-6 text-center"
        >
          <p className="text-sm text-red-300">{error}</p>
          <p className="max-w-md text-xs text-slate-500">
            The map reads from the backend at{" "}
            <code className="text-slate-400">/api/v1/dashboard/map</code>. Check that the
            API is running and reachable.
          </p>
          <Button variant="secondary" size="sm" onClick={load}>
            Try again
          </Button>
        </div>
      ) : data && data.points.length === 0 && data.checkpoints.length === 0 ? (
        <div className="flex h-[220px] flex-col items-center justify-center gap-1 rounded-xl border border-white/10 bg-[#111118] text-center">
          <p className="text-sm text-slate-300">No location data yet</p>
          <p className="text-xs text-slate-500">
            Origins are derived from a document&apos;s issuing country once a scan completes.
          </p>
        </div>
      ) : data ? (
        <>
          <OperationsMap
            data={data}
            height={height}
            onSelectScan={(id) => router.push(`/scans/${id}`)}
          />
          <p className="mt-2 text-[11px] leading-relaxed text-slate-500">{data.geocode_note}</p>
        </>
      ) : (
        <div className="h-[420px] animate-pulse rounded-xl border border-white/10 bg-[#111118]" />
      )}
    </div>
  );
}
