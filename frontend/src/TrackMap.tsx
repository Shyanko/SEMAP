import React from "react";
import { Map } from "lucide-react";
import { loadGoogleMaps } from "./googleMaps";
import type { TrackSegment } from "./types";

const DEFAULT_CENTER = { lat: 35.8617, lng: 104.1954 };
const configuredApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY?.trim() || "";
const MAP_API_KEY = configuredApiKey === "change-me" ? "" : configuredApiKey;
const configuredMapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID?.trim() || "";
const MAP_ID = configuredMapId && configuredMapId !== "change-me" ? configuredMapId : "DEMO_MAP_ID";

type MapOverlay = google.maps.marker.AdvancedMarkerElement | google.maps.Polyline;

function pointLabel(point: TrackSegment["points"][number]) {
  return point.name ?? `${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`;
}

function segmentBounds(
  maps: typeof google.maps,
  segment: TrackSegment | null,
  segments: TrackSegment[],
) {
  const bounds = new maps.LatLngBounds();
  const source = segment?.points.length ? [segment] : segments;
  let count = 0;

  for (const item of source) {
    for (const point of item.points) {
      bounds.extend({ lat: point.lat, lng: point.lng });
      count += 1;
    }
  }

  return { bounds, count };
}

export function TrackMap({
  segments,
  selectedSegment,
  onSelectSegment,
}: {
  segments: TrackSegment[];
  selectedSegment: TrackSegment | null;
  onSelectSegment: (segmentId: number) => void;
}) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const mapRef = React.useRef<google.maps.Map | null>(null);
  const overlaysRef = React.useRef<MapOverlay[]>([]);
  const [maps, setMaps] = React.useState<typeof google.maps | null>(null);
  const [markerLibrary, setMarkerLibrary] = React.useState<google.maps.MarkerLibrary | null>(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!MAP_API_KEY) {
      setError("缺少 VITE_GOOGLE_MAPS_API_KEY");
      return;
    }

    let cancelled = false;
    loadGoogleMaps(MAP_API_KEY)
      .then((libraries) => {
        if (cancelled || !containerRef.current) {
          return;
        }
        mapRef.current = new libraries.maps.Map(containerRef.current, {
          center: DEFAULT_CENTER,
          clickableIcons: false,
          fullscreenControl: false,
          mapId: MAP_ID,
          mapTypeControl: false,
          streetViewControl: false,
          zoom: 4,
        });
        setMaps(libraries.maps);
        setMarkerLibrary(libraries.marker);
        setError("");
      })
      .catch(() => setError("地图加载失败"));

    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (!maps || !markerLibrary || !mapRef.current) {
      return;
    }

    overlaysRef.current.forEach((overlay) => {
      if (overlay instanceof maps.Polyline) {
        overlay.setMap(null);
      } else {
        overlay.map = null;
      }
    });
    overlaysRef.current = [];

    for (const segment of segments) {
      if (segment.points.length === 0) {
        continue;
      }

      const selected = selectedSegment?.id === segment.id;
      const path = segment.points.map((point) => ({ lat: point.lat, lng: point.lng }));
      const line = new maps.Polyline({
        clickable: true,
        geodesic: true,
        map: mapRef.current,
        path,
        strokeColor: selected ? "#b94b42" : "#22736f",
        strokeOpacity: selected ? 0.92 : 0.42,
        strokeWeight: selected ? 5 : 3,
        zIndex: selected ? 20 : 5,
      });
      line.addListener("click", () => onSelectSegment(segment.id));
      overlaysRef.current.push(line);

      for (const point of segment.points) {
        const markerElement = document.createElement("button");
        markerElement.className = selected ? "mapMarker selected" : "mapMarker";
        markerElement.type = "button";
        markerElement.title = pointLabel(point);

        const marker = new markerLibrary.AdvancedMarkerElement({
          content: markerElement,
          gmpClickable: true,
          map: mapRef.current,
          position: { lat: point.lat, lng: point.lng },
          title: `${segment.title} · ${pointLabel(point)}`,
          zIndex: selected ? 30 : 10,
        });
        marker.addEventListener("gmp-click", () => onSelectSegment(segment.id));
        overlaysRef.current.push(marker);
      }
    }

    const { bounds, count } = segmentBounds(maps, selectedSegment, segments);
    if (count === 1) {
      mapRef.current.setCenter(bounds.getCenter());
      mapRef.current.setZoom(10);
    } else if (count > 1) {
      mapRef.current.fitBounds(bounds, 54);
    }
  }, [maps, markerLibrary, onSelectSegment, segments, selectedSegment]);

  return (
    <div className="mapFrame">
      <div className="googleMap" ref={containerRef} />
      {!maps || error ? (
        <div className="mapStatus">
          <Map size={38} />
          <span>{error || "地图加载中"}</span>
        </div>
      ) : null}
      {maps && !error && segments.length === 0 ? <div className="mapEmptyHint">暂无轨迹</div> : null}
    </div>
  );
}
