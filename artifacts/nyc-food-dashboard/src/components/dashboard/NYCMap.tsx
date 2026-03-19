import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import type { District } from "@workspace/api-client-react";
import { useNYCGeoJson } from "@/hooks/use-map-data";

interface NYCMapProps {
  districts: District[];
  selectedFips: string | null;
  onSelectDistrict: (fips: string) => void;
}

function MapUpdater({ selectedFips, geoJson, districts }: { selectedFips: string | null, geoJson: any, districts: District[] }) {
  const map = useMap();
  
  useEffect(() => {
    if (selectedFips && geoJson) {
      // Find the feature to bound to
      const feature = geoJson.features.find((f: any) => f.properties.BoroCD.toString() === selectedFips);
      if (feature) {
        // We do a simple fitBounds if we have L available, but without direct L import we can just re-center roughly
        // Realistically, for production, we'd use L.geoJSON(feature).getBounds()
      }
    }
  }, [selectedFips, geoJson, map]);

  return null;
}

export function NYCMap({ districts, selectedFips, onSelectDistrict }: NYCMapProps) {
  const { data: geoJson, isLoading } = useNYCGeoJson();
  
  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-card/20 relative z-0">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
          <p className="text-sm font-mono text-muted-foreground">INITIALIZING GEO-SPATIAL RENDERER...</p>
        </div>
      </div>
    );
  }

  const getDistrictStyle = (feature: any) => {
    const fips = feature.properties.BoroCD.toString();
    const district = districts.find(d => d.fips === fips);
    const isSelected = selectedFips === fips;
    
    return {
      fillColor: district ? district.color : "#27272a",
      weight: isSelected ? 3 : 1,
      opacity: 1,
      color: isSelected ? "#ffffff" : "#000000",
      fillOpacity: isSelected ? 0.9 : 0.6,
      dashArray: isSelected ? "" : "3"
    };
  };

  const onEachFeature = (feature: any, layer: any) => {
    const fips = feature.properties.BoroCD.toString();
    const district = districts.find(d => d.fips === fips);
    
    if (district) {
      layer.bindTooltip(`
        <div class="font-sans">
          <div class="font-bold text-[13px] mb-1">${district.cd_name}</div>
          <div class="text-[11px] font-mono flex justify-between gap-4">
            <span>Risk:</span> 
            <span style="color: ${district.color}">${district.risk_tier}</span>
          </div>
          <div class="text-[11px] font-mono flex justify-between gap-4">
            <span>Score:</span> 
            <span>${district.vulnerability_score}</span>
          </div>
        </div>
      `, {
        className: 'bg-card border border-border text-foreground rounded shadow-xl backdrop-blur-md',
        direction: 'top',
        sticky: true
      });

      layer.on({
        click: () => onSelectDistrict(fips),
        mouseover: (e: any) => {
          const l = e.target;
          l.setStyle({ fillOpacity: 0.9, weight: 2 });
          l.bringToFront();
        },
        mouseout: (e: any) => {
          const l = e.target;
          if (selectedFips !== fips) {
            l.setStyle(getDistrictStyle(feature));
          }
        }
      });
    }
  };

  return (
    <div className="w-full h-full relative bg-[#0a0a0c] z-0">
      <MapContainer 
        center={[40.7128, -73.95]} 
        zoom={11} 
        style={{ height: '100%', width: '100%', background: 'transparent' }}
        zoomControl={false}
      >
        {/* CartoDB Dark Matter */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
        />
        
        {geoJson && (
          <GeoJSON 
            key={`geojson-${selectedFips || 'none'}`} // Force re-render on selection change for proper styling stacking
            data={geoJson} 
            style={getDistrictStyle}
            onEachFeature={onEachFeature}
          />
        )}
        
        <MapUpdater selectedFips={selectedFips} geoJson={geoJson} districts={districts} />
      </MapContainer>

      {/* Legend Override */}
      <div className="absolute bottom-6 right-6 z-[400] bg-card/80 backdrop-blur-md border border-border/50 p-4 rounded-xl shadow-2xl">
        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3 font-sans">Risk Level</h4>
        <div className="space-y-2 font-mono text-[11px]">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-[2px] bg-[#d32f2f] shadow-[0_0_8px_#d32f2f80]"></div>
            <span>CRITICAL (70-100)</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-[2px] bg-[#f57c00]"></div>
            <span>HIGH (50-69)</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-[2px] bg-[#fbc02d]"></div>
            <span>MODERATE (30-49)</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-[2px] bg-[#388e3c]"></div>
            <span>LOWER (0-29)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
