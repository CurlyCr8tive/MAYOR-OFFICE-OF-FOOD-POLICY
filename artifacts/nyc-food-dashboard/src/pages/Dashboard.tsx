import { useState } from "react";
import { useGetDistricts } from "@workspace/api-client-react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { NYCMap } from "@/components/dashboard/NYCMap";
import { DetailPanel } from "@/components/dashboard/DetailPanel";
import { RightPanel } from "@/components/dashboard/RightPanel";

export default function Dashboard() {
  const [selectedFips, setSelectedFips] = useState<string | null>(null);
  
  // Use generated API hook
  const { data, isLoading, error } = useGetDistricts();

  if (isLoading) {
    return (
      <div className="h-screen w-full bg-background flex flex-col items-center justify-center text-primary font-mono gap-4">
        <div className="w-16 h-16 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
        <p className="tracking-widest animate-pulse">CONNECTING TO DATABANKS...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="h-screen w-full bg-background flex flex-col items-center justify-center text-destructive font-mono gap-4">
        <p className="text-xl font-bold uppercase">System Error</p>
        <p className="text-sm opacity-70">Failed to retrieve vulnerability telemetry.</p>
        <button 
          onClick={() => window.location.reload()}
          className="px-6 py-2 bg-destructive/20 border border-destructive rounded text-destructive hover:bg-destructive hover:text-white transition-colors mt-4"
        >
          RETRY CONNECTION
        </button>
      </div>
    );
  }

  const { districts, metadata } = data;
  const selectedDistrict = selectedFips ? districts.find(d => d.fips === selectedFips) : undefined;

  return (
    <div className="h-screen w-full bg-background flex flex-col overflow-hidden text-foreground selection:bg-primary/30">
      <Header />
      
      <main className="flex-1 flex overflow-hidden min-h-0 relative z-0">
        <Sidebar 
          districts={districts} 
          selectedFips={selectedFips} 
          onSelectDistrict={setSelectedFips} 
        />
        
        <div className="flex-1 flex flex-col min-w-0 relative z-0">
          <div className="flex-1 min-h-0 relative z-0">
            <NYCMap 
              districts={districts} 
              selectedFips={selectedFips} 
              onSelectDistrict={setSelectedFips} 
            />
          </div>
          
          <DetailPanel district={selectedDistrict} />
        </div>
        
        <RightPanel />
      </main>

      <Footer criticalCount={metadata.critical_count} />
    </div>
  );
}
