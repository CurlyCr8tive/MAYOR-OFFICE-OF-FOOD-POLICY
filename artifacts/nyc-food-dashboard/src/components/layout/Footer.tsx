import { Activity, Users, MapPin, AlertTriangle } from "lucide-react";

export function Footer({ criticalCount }: { criticalCount: number }) {
  return (
    <footer className="h-10 border-t border-border/50 bg-card/80 backdrop-blur-md flex items-center justify-between px-6 z-50 shrink-0 text-xs font-mono">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors cursor-default">
          <Activity className="w-4 h-4 text-blue-400" />
          <span>MODEL v2.1.4</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors cursor-default">
          <Users className="w-4 h-4 text-emerald-400" />
          <span>1.8M SNAP RECIPIENTS</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors cursor-default">
          <AlertTriangle className="w-4 h-4 text-red-500" />
          <span>{criticalCount} CRITICAL DISTRICTS</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors cursor-default">
          <MapPin className="w-4 h-4 text-orange-400" />
          <span>700+ PANTRIES ACTIVE</span>
        </div>
      </div>

      <div className="text-muted-foreground/60">
        CONFIDENTIAL - INTERNAL GOV USE ONLY
      </div>
    </footer>
  );
}
