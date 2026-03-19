import { useQuery } from "@tanstack/react-query";

// GeoJSON for NYC Community Districts
const GEOJSON_URL = "https://raw.githubusercontent.com/dwillis/nyc-maps/master/community_districts.geojson";

export function useNYCGeoJson() {
  return useQuery({
    queryKey: ["nyc-community-districts-geojson"],
    queryFn: async () => {
      const res = await fetch(GEOJSON_URL);
      if (!res.ok) throw new Error("Failed to fetch NYC GeoJSON");
      return res.json();
    },
    staleTime: Infinity, // GeoJSON rarely changes
  });
}
