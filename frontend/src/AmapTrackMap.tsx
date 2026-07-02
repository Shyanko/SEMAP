import React from "react";
import { Map } from "lucide-react";
import { loadAmap, type AMapMap, type AMapOverlay } from "./amap";
import type { TrackSegment } from "./types";

const DEFAULT_CENTER: [number, number] = [104.1954, 35.8617];
const configuredApiKey = import.meta.env.VITE_AMAP_JS_API_KEY?.trim() || "";
const AMAP_API_KEY = configuredApiKey === "change-me" ? "" : configuredApiKey;
const configuredSecurityCode = import.meta.env.VITE_AMAP_SECURITY_JS_CODE?.trim() || "";
const AMAP_SECURITY_JS_CODE =
  configuredSecurityCode === "change-me" ? "" : configuredSecurityCode;

function pointLabel(point: TrackSegment["points"][number]) {
  return point.name ?? `${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`;
}

function markerPoints(segment: TrackSegment) {
  return segment.points.filter((point, index) => {
    if (segment.sourceType === "train") {
      return index === 0 || index === segment.points.length - 1;
    }
    return Boolean(point.name);
  });
}

function selectedBounds(segment: TrackSegment | null, segments: TrackSegment[]) {
  const source = segment?.points.length ? [segment] : segments;
  const points = source.flatMap((item) => item.points);
  return points.length ? points : [];
}

export function AmapTrackMap({
  segments,
  selectedSegment,
  onSelectSegment,
}: {
  segments: TrackSegment[];
  selectedSegment: TrackSegment | null;
  onSelectSegment: (segmentId: number | null) => void;
}) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const mapRef = React.useRef<AMapMap | null>(null);
  const overlaysRef = React.useRef<AMapOverlay[]>([]);
  const [amap, setAmap] = React.useState<Awaited<ReturnType<typeof loadAmap>> | null>(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!AMAP_API_KEY || !AMAP_SECURITY_JS_CODE) {
      setError("缺少 VITE_AMAP_JS_API_KEY 或 VITE_AMAP_SECURITY_JS_CODE");
      return;
    }

    let cancelled = false;
    loadAmap(AMAP_API_KEY, AMAP_SECURITY_JS_CODE)
      .then((nextAmap) => {
        if (cancelled || !containerRef.current) {
          return;
        }
        const map = new nextAmap.Map(containerRef.current, {
          center: DEFAULT_CENTER,
          resizeEnable: true,
          viewMode: "2D",
          zoom: 4,
        });
        mapRef.current = map;
        setAmap(nextAmap);
        setError("");
      })
      .catch(() => setError("高德地图加载失败"));

    return () => {
      cancelled = true;
      mapRef.current?.destroy();
      mapRef.current = null;
    };
  }, []);

  React.useEffect(() => {
    if (!amap || !mapRef.current) {
      return;
    }

    if (overlaysRef.current.length > 0) {
      mapRef.current.remove(overlaysRef.current);
      overlaysRef.current = [];
    }

    const selectedOverlays: AMapOverlay[] = [];

    for (const segment of segments) {
      if (segment.points.length === 0) {
        continue;
      }

      const selected = selectedSegment?.id === segment.id;
      const segmentOverlays: AMapOverlay[] = [];
      const path = segment.points.map((point) => [point.lng, point.lat] as [number, number]);
      const line = new amap.Polyline({
        bubble: true,
        map: mapRef.current,
        path,
        strokeColor: selected ? "#b94b42" : "#22736f",
        strokeOpacity: selected ? 0.92 : 0.42,
        strokeWeight: selected ? 5 : 3,
        zIndex: selected ? 20 : 5,
      });
      line.on("click", () => onSelectSegment(segment.id));
      overlaysRef.current.push(line);
      segmentOverlays.push(line);

      for (const point of markerPoints(segment)) {
        const markerElement = document.createElement("button");
        markerElement.className = selected ? "mapMarker selected" : "mapMarker";
        markerElement.type = "button";
        markerElement.title = pointLabel(point);

        const marker = new amap.Marker({
          anchor: "center",
          content: markerElement,
          map: mapRef.current,
          position: [point.lng, point.lat],
          title: `${segment.title} · ${pointLabel(point)}`,
          zIndex: selected ? 30 : 10,
        });
        marker.on("click", () => onSelectSegment(segment.id));
        overlaysRef.current.push(marker);
        segmentOverlays.push(marker);
      }

      if (selected) {
        selectedOverlays.push(...segmentOverlays);
      }
    }

    const points = selectedBounds(selectedSegment, segments);
    if (points.length === 1) {
      mapRef.current.setCenter([points[0].lng, points[0].lat]);
      mapRef.current.setZoom(10);
    } else {
      const fitOverlays = selectedOverlays.length > 0 ? selectedOverlays : overlaysRef.current;
      if (fitOverlays.length > 0) {
        window.requestAnimationFrame(() => {
          mapRef.current?.setFitView(fitOverlays, true, [54, 54, 54, 54]);
        });
      }
    }
  }, [amap, onSelectSegment, segments, selectedSegment]);

  return (
    <>
      <div className="trackMapCanvas" ref={containerRef} />
      {!amap || error ? (
        <div className="mapStatus">
          <Map size={38} />
          <span>{error || "地图加载中"}</span>
        </div>
      ) : null}
      {amap && !error && segments.length === 0 ? <div className="mapEmptyHint">暂无轨迹</div> : null}
    </>
  );
}
