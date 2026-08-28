import { useState, useEffect, useCallback, useRef } from "react";
import { getVehicleRoute, getVehicleRouteGeoJSON, getVehicleRouteSummary } from "../api/routes";
import { getVehicleHistory } from "../api/sightings";
import { RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection, Sighting } from "../types/api";
import { DEMO_ROUTE_GJ01AB1234, DEMO_SIGHTINGS } from "../utils/demoData";

export function useTrajectory(registration: string, demoMode = false) {
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [summary, setSummary] = useState<RouteSummaryResponse | null>(null);
  const [geoJSON, setGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeReqRef = useRef<string>("");

  const fetchTrajectory = useCallback(async (reg: string) => {
    const cleanReg = reg.trim().toUpperCase();
    if (!cleanReg) {
      setRoute(null);
      setSummary(null);
      setGeoJSON(null);
      setSightings([]);
      setError(null);
      return;
    }

    activeReqRef.current = cleanReg;
    setLoading(true);
    setError(null);

    if (demoMode && (cleanReg === "GJ01AB1234" || cleanReg.includes("1234"))) {
      setRoute(DEMO_ROUTE_GJ01AB1234);
      setSightings(DEMO_SIGHTINGS);
      setSummary({
        registration: cleanReg,
        status: DEMO_ROUTE_GJ01AB1234.status,
        confidence: DEMO_ROUTE_GJ01AB1234.trajectory_confidence,
        total_distance_km: DEMO_ROUTE_GJ01AB1234.total_lower_bound_distance_m / 1000,
        duration_minutes: DEMO_ROUTE_GJ01AB1234.duration_seconds / 60,
        avg_speed_kmh: DEMO_ROUTE_GJ01AB1234.minimum_average_speed_kmh,
        sighting_count: DEMO_ROUTE_GJ01AB1234.sighting_count,
        camera_count: DEMO_ROUTE_GJ01AB1234.camera_count,
        reasons: DEMO_ROUTE_GJ01AB1234.reasons,
        warnings: DEMO_ROUTE_GJ01AB1234.warnings,
        disclaimer: DEMO_ROUTE_GJ01AB1234.disclaimer,
      });

      // Construct synthetic GeoJSON
      const coords = DEMO_ROUTE_GJ01AB1234.sightings
        .filter((s) => s.longitude && s.latitude)
        .map((s) => [s.longitude!, s.latitude!]);

      setGeoJSON({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            geometry: { type: "LineString", coordinates: coords },
            properties: { registration: cleanReg, status: DEMO_ROUTE_GJ01AB1234.status },
          },
          ...DEMO_ROUTE_GJ01AB1234.sightings.map((s, idx) => ({
            type: "Feature" as const,
            geometry: { type: "Point" as const, coordinates: [s.longitude!, s.latitude!] },
            properties: {
              sequence: idx + 1,
              sighting_id: s.sighting_id,
              camera_id: s.camera_id,
              event_time_utc: s.event_time_utc,
              match_score: s.match_score,
            },
          })),
        ],
        properties: { registration: cleanReg },
      });

      setLoading(false);
      return;
    }

    try {
      const [rt, sm, gj, hist] = await Promise.all([
        getVehicleRoute(cleanReg).catch(() => null),
        getVehicleRouteSummary(cleanReg).catch(() => null),
        getVehicleRouteGeoJSON(cleanReg).catch(() => null),
        getVehicleHistory(cleanReg).catch(() => null),
      ]);

      // Guard against race conditions when user types quickly
      if (activeReqRef.current !== cleanReg) return;

      if (!rt && (!hist || hist.sightings.length === 0)) {
        setRoute(null);
        setSummary(null);
        setGeoJSON(null);
        setSightings([]);
        setError(`No sightings or movement trajectory found for vehicle '${cleanReg}'.`);
      } else {
        setRoute(rt);
        setSummary(sm);
        setGeoJSON(gj);
        setSightings(hist?.sightings || []);
        setError(null);
      }
    } catch (e: any) {
      if (activeReqRef.current === cleanReg) {
        setError(e.message || "Failed to load vehicle trajectory.");
      }
    } finally {
      if (activeReqRef.current === cleanReg) {
        setLoading(false);
      }
    }
  }, [demoMode]);

  useEffect(() => {
    fetchTrajectory(registration);
  }, [registration, fetchTrajectory]);

  return { route, summary, geoJSON, sightings, loading, error, refresh: () => fetchTrajectory(registration) };
}
