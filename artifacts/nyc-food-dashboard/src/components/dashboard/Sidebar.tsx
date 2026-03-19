import { useState } from "react";
import { Search, Map as MapIcon, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { District } from "@workspace/api-client-react";

interface SidebarProps {
  districts: District[];
  selectedFips: string | null;
  onSelectDistrict: (fips: string) => void;
}

const BOROUGHS = ["All", "Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"];

export function Sidebar({ districts, selectedFips, onSelectDistrict }: SidebarProps) {
  const [search, setSearch] = useState("");
  const [activeBorough, setActiveBorough] = useState("All");

  const filtered = districts.filter(d => {
    const matchSearch = d.cd_name.toLowerCase().includes(search.toLowerCase()) || 
                        d.fips.includes(search);
    const matchBorough = activeBorough === "All" || d.borough === activeBorough;
    return matchSearch && matchBorough;
  });

  return (
    <div className="w-80 flex-shrink-0 border-r border-border/50 bg-card/30 flex flex-col h-full backdrop-blur-sm z-10">
      <div className="p-4 border-b border-border/50 space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search districts or FIPS..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-background border border-border rounded-md pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all text-foreground placeholder:text-muted-foreground/50"
          />
        </div>
        
        <div className="flex flex-wrap gap-1.5">
          {BOROUGHS.map(b => (
            <button
              key={b}
              onClick={() => setActiveBorough(b)}
              className={`px-2.5 py-1 text-[10px] font-medium uppercase tracking-wider rounded-md transition-all ${
                activeBorough === b 
                  ? "bg-primary text-primary-foreground shadow-[0_0_10px_rgba(37,99,235,0.3)] border-primary" 
                  : "bg-secondary text-muted-foreground border-transparent hover:bg-secondary/80 border hover:border-border"
              }`}
            >
              {b}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        <AnimatePresence>
          {filtered.map((d, i) => (
            <motion.button
              key={d.fips}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02, duration: 0.2 }}
              onClick={() => onSelectDistrict(d.fips)}
              className={`w-full text-left px-3 py-3 rounded-lg border transition-all group flex items-center justify-between ${
                selectedFips === d.fips
                  ? "bg-primary/10 border-primary shadow-[inset_4px_0_0_0_var(--color-primary)]"
                  : "bg-transparent border-transparent hover:bg-secondary/50 hover:border-border"
              }`}
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <div 
                    className="w-2 h-2 rounded-full" 
                    style={{ backgroundColor: d.color, boxShadow: `0 0 8px ${d.color}` }}
                  />
                  <span className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors">
                    {d.cd_name}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono">
                  <span>FIPS: {d.fips}</span>
                  <span>SCORE: <span className="text-foreground">{d.vulnerability_score.toFixed(1)}</span></span>
                </div>
              </div>
              <ChevronRight className={`w-4 h-4 transition-transform ${selectedFips === d.fips ? "text-primary translate-x-1" : "text-muted-foreground opacity-0 group-hover:opacity-100"}`} />
            </motion.button>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-8 text-muted-foreground text-sm flex flex-col items-center">
              <MapIcon className="w-8 h-8 mb-2 opacity-20" />
              No districts found
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
