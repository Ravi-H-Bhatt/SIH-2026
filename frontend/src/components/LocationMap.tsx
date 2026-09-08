"use client";

import React, { useEffect, useRef } from "react";

interface LocationMapProps {
  latitude?: number;
  longitude?: number;
  address?: string;
  checkpointName?: string;
  markerTitle?: string;
}

/**
 * Geolocation Map Component
 * Shows document address and checkpoint location
 * Uses Mapbox GL or Google Maps
 */
export const LocationMap: React.FC<LocationMapProps> = ({
  latitude = 28.7041, // Delhi default
  longitude = 77.1025,
  address = "New Delhi, India",
  checkpointName = "Gate 04",
  markerTitle = "Document Address",
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const [mapReady, setMapReady] = React.useState(false);

  useEffect(() => {
    if (!mapContainer.current) return;

    // Initialize map (Mapbox GL)
    const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    
    if (!mapboxToken) {
      // Fallback to simple coordinates display
      renderSimpleMap();
      return;
    }

    // Load Mapbox GL library
    const script = document.createElement("script");
    script.src = "https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js";
    script.async = true;
    script.onload = () => {
      const link = document.createElement("link");
      link.href = "https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css";
      link.rel = "stylesheet";
      document.head.appendChild(link);

      try {
        // Declare mapboxgl type
        const mapboxgl = (window as any).mapboxgl;
        mapboxgl.accessToken = mapboxToken;
        const map = new mapboxgl.Map({
          container: mapContainer.current,
          style: "mapbox://styles/mapbox/dark-v11",
          center: [longitude, latitude],
          zoom: 10,
          pitch: 20,
          bearing: -35,
        });

        // Add markers
        new mapboxgl.Marker({ color: "#3B82F6" })
          .setLngLat([longitude, latitude])
          .setPopup(new mapboxgl.Popup().setHTML(`<strong>${markerTitle}</strong><br>${address}`))
          .addTo(map);

        map.on("load", () => setMapReady(true));
      } catch (err) {
        console.warn("Mapbox initialization failed:", err);
        renderSimpleMap();
      }
    };
    document.head.appendChild(script);
  }, [latitude, longitude, address, markerTitle]);

  const renderSimpleMap = () => {
    if (!mapContainer.current) return;
    const latStr = latitude.toFixed(4);
    const lngStr = longitude.toFixed(4);
    mapContainer.current.innerHTML = `
      <div style="
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        color: #F8FAFC;
        padding: 20px;
        text-align: center;
        border-radius: 12px;
      ">
        <div style="font-size: 24px; margin-bottom: 12px;">📍</div>
        <div style="font-weight: 600; margin-bottom: 4px;">${markerTitle}</div>
        <div style="font-size: 14px; color: #94A3B8; margin-bottom: 16px;">${address}</div>
        <div style="font-size: 12px; color: #64748B;">
          <div>Latitude: ${latStr}°</div>
          <div>Longitude: ${lngStr}°</div>
        </div>
      </div>
    `;
  };

  return (
    <div
      ref={mapContainer}
      style={{
        width: "100%",
        height: "300px",
        borderRadius: "12px",
        overflow: "hidden",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        backgroundColor: "#0F172A",
      }}
    />
  );
};

/**
 * Enhanced Location Display Card
 */
export const LocationCard: React.FC<LocationMapProps> = ({
  latitude,
  longitude,
  address,
  checkpointName,
}) => {
  return (
    <div
      style={{
        backgroundColor: "rgba(30, 41, 59, 0.8)",
        border: "1px solid rgba(59, 130, 246, 0.2)",
        borderRadius: "12px",
        padding: "20px",
        marginTop: "16px",
      }}
    >
      <h3 style={{ fontSize: "13px", fontWeight: 600, margin: "0 0 12px", textTransform: "uppercase", opacity: 0.7 }}>
        📍 Location Information
      </h3>
      
      <LocationMap
        latitude={latitude}
        longitude={longitude}
        address={address}
        checkpointName={checkpointName}
      />

      <div style={{ marginTop: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
          <span style={{ opacity: 0.7 }}>Document Address:</span>
          <span style={{ fontWeight: 500 }}>{address}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
          <span style={{ opacity: 0.7 }}>Checkpoint:</span>
          <span style={{ fontWeight: 500 }}>{checkpointName}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
          <span style={{ opacity: 0.7 }}>Latitude:</span>
          <span style={{ fontWeight: 500 }}>{latitude?.toFixed(4)}°</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ opacity: 0.7 }}>Longitude:</span>
          <span style={{ fontWeight: 500 }}>{longitude?.toFixed(4)}°</span>
        </div>
      </div>
    </div>
  );
};

export default LocationMap;
