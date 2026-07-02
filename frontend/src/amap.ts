export type AMapOverlay = {
  on(eventName: string, handler: () => void): void;
};

export type AMapMap = {
  destroy(): void;
  remove(overlays: AMapOverlay[]): void;
  setCenter(center: [number, number]): void;
  setFitView(overlays?: AMapOverlay[], immediately?: boolean, avoid?: number[], maxZoom?: number): void;
  setZoom(zoom: number): void;
};

type AMapApi = {
  Map: new (
    container: HTMLElement,
    options: {
      center: [number, number];
      dragEnable?: boolean;
      resizeEnable?: boolean;
      scrollWheel?: boolean;
      viewMode?: "2D" | "3D";
      zoom: number;
    },
  ) => AMapMap;
  Marker: new (options: {
    anchor?: "top-left" | "top-center" | "top-right" | "middle-left" | "center" | "middle-right" | "bottom-left" | "bottom-center" | "bottom-right";
    content?: HTMLElement;
    map: AMapMap;
    position: [number, number];
    title?: string;
    zIndex?: number;
  }) => AMapOverlay;
  Polyline: new (options: {
    bubble?: boolean;
    isOutline?: boolean;
    map: AMapMap;
    path: [number, number][];
    showDir?: boolean;
    strokeColor: string;
    strokeOpacity: number;
    strokeWeight: number;
    zIndex?: number;
  }) => AMapOverlay;
};

declare global {
  interface Window {
    AMap?: AMapApi;
    _AMapSecurityConfig?: {
      securityJsCode: string;
    };
  }
}

let amapPromise: Promise<AMapApi> | null = null;

export function loadAmap(apiKey: string, securityJsCode: string) {
  if (window.AMap) {
    return Promise.resolve(window.AMap);
  }

  if (!amapPromise) {
    if (securityJsCode) {
      window._AMapSecurityConfig = { securityJsCode };
    }

    amapPromise = new Promise<AMapApi>((resolve, reject) => {
      const existingScript = document.getElementById("amap-jsapi");
      if (existingScript) {
        existingScript.addEventListener("load", () => {
          if (window.AMap) {
            resolve(window.AMap);
          } else {
            reject(new Error("AMap JSAPI loaded without AMap global"));
          }
        });
        existingScript.addEventListener("error", () => reject(new Error("AMap JSAPI failed")));
        return;
      }

      const script = document.createElement("script");
      script.id = "amap-jsapi";
      script.async = true;
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(apiKey)}`;
      script.onload = () => {
        if (window.AMap) {
          resolve(window.AMap);
        } else {
          reject(new Error("AMap JSAPI loaded without AMap global"));
        }
      };
      script.onerror = () => {
        amapPromise = null;
        reject(new Error("AMap JSAPI failed"));
      };
      document.head.appendChild(script);
    });
  }

  return amapPromise;
}
