import { useState, useEffect, useCallback, useRef } from "react";
import { getVehicleRoute, getVehicleRouteGeoJSON, getVehicleRouteSummary } from "../api/routes";
import { getVehicleHistory } from "../api/sightings";
import { RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection, Sighting } from "../types/api";

export function useTrajectory(registration: string) {
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
  }, []);

  useEffect(() => {
    fetchTrajectory(registration);
  }, [registration, fetchTrajectory]);

  return { route, summary, geoJSON, sightings, loading, error, refresh: () => fetchTrajectory(registration) };
}
