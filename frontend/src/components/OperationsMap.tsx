"use client";

import * as React from "react";
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";

import type { OperationsMapData, MapPoint, MapCheckpoint } from "@/types";

/**
 * Operations map — checkpoints plus one origin marker per recent scan.
 *
 * Deliberately uses OpenStreetMap raster tiles rather than Mapbox. The previous
 * LocationMap component injected Mapbox GL from a CDN and required
 * NEXT_PUBLIC_MAPBOX_TOKEN; with no token it silently fell back to printing
 * coordinates as text, which is why no map ever appeared on any dashboard.
 * OSM needs no credentials, so there is no configuration that can go missing.
 *
 * Markers are built with L.divIcon (pure CSS) instead of Leaflet's default PNG
 * icons, which avoids the well-known bundler issue where marker images 404.
 */

const RISK_COLORS: Record<string, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#ef4444",
  critical: "#dc2626",
};

function riskColor(level?: string | null): string {
  return RISK_COLORS[(level || "low").toLowerCase()] ?? "#64748b";
}

/** Checkpoint pin: a labelled shield, visually distinct from scan origins. */
function checkpointIcon(flagged: number): L.DivIcon {
  const alert = flagged > 0;
  return L.divIcon({
    className: "",
    html: `
      <div style="
        display:flex;align-items:center;justify-content:center;
        width:30px;height:30px;border-radius:9px;
        background:linear-gradient(135deg,#6366f1,#4f46e5);
        border:2px solid ${alert ? "#f87171" : "rgba(255,255,255,.85)"};
        box-shadow:0 3px 10px rgba(0,0,0,.55);
        font-size:15px;line-height:1;">🛂</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -16],
  });
}

/** Refits the viewport whenever the plotted set changes. */
function FitBounds({ points, checkpoints }: { points: MapPoint[]; checkpoints: MapCheckpoint[] }) {
  const map = useMap();

  React.useEffect(() => {
    const coords: [number, number][] = [
      ...checkpoints.map((c) => [c.latitude, c.longitude] as [number, number]),
      ...points.map((p) => [p.latitude, p.longitude] as [number, number]),
    ].filter(([lat, lng]) => Number.isFinite(lat) && Number.isFinite(lng));

    if (coords.length === 0) return;
    if (coords.length === 1) {
      map.setView(coords[0], 5);
      return;
    }
    map.fitBounds(L.latLngBounds(coords).pad(0.18), { animate: false });
  }, [map, points, checkpoints]);

  return null;
}

export interface OperationsMapProps {
  data: OperationsMapData;
  height?: number | string;
  /** Called when an origin marker is clicked — used to deep-link to the scan. */
  onSelectScan?: (scanId: string) => void;
}

export default function OperationsMap({ data, height = 420, onSelectScan }: OperationsMapProps) {
  const { points = [], checkpoints = [] } = data;

  // Multiple travellers share a country centroid, so stack counts per location
  // instead of drawing 12 identical markers on top of each other.
  const grouped = React.useMemo(() => {
    const map = new Map<string, MapPoint[]>();
    for (const p of points) {
      const key = `${p.latitude.toFixed(3)},${p.longitude.toFixed(3)}`;
      const bucket = map.get(key);
      if (bucket) bucket.push(p);
      else map.set(key, [p]);
    }
    return [...map.values()];
  }, [points]);

  return (
    <div
      className="relative overflow-hidden rounded-xl border border-white/10"
      style={{ height }}
      // The map is a supplementary visualisation of data already listed in the
      // tables below it, so it is hidden from the a11y tree rather than being
      // an unlabelled interactive region.
      role="presentation"
    >
      <MapContainer
        center={[22, 78]}
        zoom={3}
        minZoom={2}
        scrollWheelZoom={false}
        worldCopyJump
        style={{ height: "100%", width: "100%", background: "#0a0a0f" }}
        attributionControl
      >
        {/*
          Plain OpenStreetMap tiles. CARTO's dark_all basemap now stamps
          "API KEY REQUIRED" across every tile on unkeyed use, so it is not
          usable as an anonymous basemap. OSM needs no key; the dark styling is
          applied in CSS via .map-dark-tiles instead of relying on a hosted
          dark style, which keeps the map free of credentials entirely.
        */}
        <TileLayer
          className="map-dark-tiles"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
        />

        <FitBounds points={points} checkpoints={checkpoints} />

        {checkpoints.map((c) => (
          <Marker
            key={c.id}
            position={[c.latitude, c.longitude]}
            icon={checkpointIcon(c.flagged)}
          >
            <Tooltip direction="top" offset={[0, -14]}>{c.name}</Tooltip>
            <Popup>
              <div className="min-w-[190px] text-slate-900">
                <div className="mb-1 text-sm font-bold">{c.name}</div>
                <div className="text-xs">Checkpoint</div>
                <hr className="my-2 border-slate-200" />
                <div className="flex justify-between text-xs">
                  <span>Total scans</span>
                  <strong>{c.total_scans}</strong>
                </div>
                <div className="flex justify-between text-xs">
                  <span>Flagged</span>
                  <strong className={c.flagged > 0 ? "text-red-600" : ""}>{c.flagged}</strong>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {grouped.map((bucket) => {
          const head = bucket[0];
          // Show the worst risk present at this location.
          const worst = bucket.reduce((acc, p) => {
            const order = ["low", "medium", "high", "critical"];
            return order.indexOf((p.risk_level || "low").toLowerCase()) >
              order.indexOf((acc.risk_level || "low").toLowerCase())
              ? p
              : acc;
          }, head);
          const color = riskColor(worst.risk_level);
          const alerting = bucket.some((p) => p.is_criminal || p.is_wanted);

          return (
            <CircleMarker
              key={`${head.latitude},${head.longitude}`}
              center={[head.latitude, head.longitude]}
              radius={Math.min(8 + bucket.length * 2, 18)}
              pathOptions={{
                color: alerting ? "#fca5a5" : color,
                weight: alerting ? 3 : 2,
                fillColor: color,
                fillOpacity: 0.55,
              }}
            >
              <Tooltip direction="top">
                {bucket.length === 1
                  ? `${head.holder_name} — ${head.country_name || head.issuing_country || "Unknown"}`
                  : `${bucket.length} travellers — ${head.country_name || head.issuing_country}`}
              </Tooltip>
              <Popup>
                <div className="max-h-64 min-w-[230px] overflow-y-auto text-slate-900">
                  <div className="mb-1 text-sm font-bold">
                    {head.country_name || head.issuing_country || "Unknown origin"}
                  </div>
                  <div className="mb-2 text-[11px] text-slate-500">
                    Country of issue (centroid, not an address)
                  </div>
                  {bucket.map((p) => (
                    <button
                      key={p.scan_id}
                      type="button"
                      onClick={() => onSelectScan?.(p.scan_id)}
                      className="mb-1 block w-full rounded border border-slate-200 p-1.5 text-left hover:bg-slate-100"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold">{p.holder_name}</span>
                        <span
                          className="rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase text-white"
                          style={{ background: riskColor(p.risk_level) }}
                        >
                          {p.risk_level}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-600">
                        {p.document_type} · {p.document_number}
                      </div>
                      {(p.is_criminal || p.is_wanted) && (
                        <div className="mt-0.5 text-[11px] font-bold text-red-600">
                          {p.is_criminal ? "🚨 CRIMINAL" : "⚠️ WANTED"}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Legend — sits above the map pane; Leaflet panes start at z-index 400 */}
      <div className="pointer-events-none absolute bottom-2 left-2 z-[500] rounded-lg border border-white/10 bg-[#0a0a0f]/85 px-2.5 py-2 backdrop-blur">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          Risk level
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {(["low", "medium", "high", "critical"] as const).map((lvl) => (
            <span key={lvl} className="flex items-center gap-1 text-[11px] text-slate-300">
              <span
                className="inline-block size-2 rounded-full"
                style={{ background: riskColor(lvl) }}
              />
              {lvl}
            </span>
          ))}
          <span className="flex items-center gap-1 text-[11px] text-slate-300">
            <span className="text-xs leading-none">🛂</span> checkpoint
          </span>
        </div>
      </div>
    </div>
  );
}
