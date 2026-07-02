import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

type GoogleMapsLibraries = {
  maps: typeof google.maps;
  marker: google.maps.MarkerLibrary;
};

let mapsPromise: Promise<GoogleMapsLibraries> | null = null;

export function loadGoogleMaps(apiKey: string) {
  if (!mapsPromise) {
    setOptions({ key: apiKey, v: "weekly" });
    mapsPromise = Promise.all([
      importLibrary("maps") as Promise<google.maps.MapsLibrary>,
      importLibrary("marker") as Promise<google.maps.MarkerLibrary>,
    ]).then(([, marker]) => ({ maps: google.maps, marker }));
  }
  return mapsPromise;
}
