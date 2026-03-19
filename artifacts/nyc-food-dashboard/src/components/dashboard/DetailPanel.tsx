import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line
} from "recharts";
import type { District } from "@workspace/api-client-react";
import { LayoutDashboard } from "lucide-react";
import { motion } from "framer-motion";

interface DetailPanelProps {
  district: District | undefined;
}

export function DetailPanel({ district }: DetailPanelProps) {
  if (!district) {
    return (
      <div className="h-64 border-t border-border/50 bg-card/40 flex flex-col items-center justify-center text-muted-foreground relative overflow-hidden backdrop-blur-md shrink-0">
        <LayoutDashboard className="w-10 h-10 mb-3 opacity-20" />
        <p className="text-sm font-medium">AWAITING DISTRICT SELECTION</p>
        <p className="text-xs font-mono opacity-50 mt-1">CLICK ON MAP OR SIDEBAR</p>
      </div>
    );
  }

  const indicators = [
    { name: "SNAP Households", value: district.indicators.snap_household_pct || 0, color: "#3b82f6" },
    { name: "Child Poverty", value: district.indicators.child_poverty_pct || 0, color: "#ec4899" },
    { name: "Rent Burden", value: district.indicators.rent_burden_pct || 0, color: "#f59e0b" },
    { name: "Unemployment", value: district.indicators.unemployment_pct || 0, color: "#ef4444" },
    { name: "Non-Citizen", value: district.indicators.noncitizen_pct || 0, color: "#8b5cf6" },
  ];

  // Mock trend data for sparkline
  const trendData = Array.from({ length: 12 }).map((_, i) => ({
    month: i,
    value: (district.indicators.snap_household_pct || 20) + Math.sin(i) * 5 + (i * 0.5)
  }));

  return (
    <motion.div 
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      key={district.fips}
      className="h-64 border-t border-border/50 bg-card/80 backdrop-blur-xl shrink-0 flex p-6 gap-8 relative overflow-hidden"
    >
      {/* Background glow matching risk tier */}
      <div 
        className="absolute top-0 left-0 w-full h-1 blur-md opacity-50"
        style={{ backgroundColor: district.color }}
      />
      
      {/* Left: Score & Meta */}
      <div className="w-64 flex flex-col justify-between border-r border-border/50 pr-8">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground leading-tight">
            {district.cd_name}
          </h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-mono text-muted-foreground">{district.borough.toUpperCase()}</span>
            <span className="text-xs font-mono text-muted-foreground border-l border-border pl-2">CD {district.fips}</span>
          </div>
        </div>

        <div>
          <div className="text-[10px] font-bold text-muted-foreground font-mono tracking-wider mb-1">VULNERABILITY SCORE</div>
          <div className="flex items-baseline gap-3">
            <span className="text-5xl font-mono font-bold leading-none tracking-tighter" style={{ color: district.color }}>
              {district.vulnerability_score.toFixed(1)}
            </span>
            <span className="text-sm font-medium uppercase tracking-widest px-2 py-0.5 rounded border border-current" style={{ color: district.color }}>
              {district.risk_tier}
            </span>
          </div>
        </div>
      </div>

      {/* Middle: Bar Charts */}
      <div className="flex-1 min-w-0">
        <h3 className="text-xs font-bold text-muted-foreground font-mono tracking-wider mb-4">KEY INDICATORS (%)</h3>
        <div className="h-[140px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={indicators} layout="vertical" margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
              <XAxis type="number" domain={[0, 100]} hide />
              <YAxis 
                type="category" 
                dataKey="name" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fill: '#71717a', fontSize: 11, fontFamily: 'Inter' }}
                width={110}
              />
              <Tooltip 
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', fontSize: '12px' }}
                itemStyle={{ color: '#fff', fontFamily: 'JetBrains Mono' }}
                formatter={(val: number) => [`${val.toFixed(1)}%`, '']}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                {indicators.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Right: Trend Sparkline */}
      <div className="w-64 flex flex-col justify-between pl-8 border-l border-border/50">
        <div>
          <h3 className="text-xs font-bold text-muted-foreground font-mono tracking-wider mb-1">SNAP TREND (12 MO)</h3>
          <p className="text-xs text-muted-foreground">Projected impact of federal cuts</p>
        </div>
        <div className="h-24 w-full mt-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke={district.color} 
                strokeWidth={2} 
                dot={false}
                activeDot={{ r: 4, fill: district.color, stroke: '#18181b' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </motion.div>
  );
}
