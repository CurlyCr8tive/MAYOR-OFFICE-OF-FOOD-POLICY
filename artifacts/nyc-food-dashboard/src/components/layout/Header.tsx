import { ShieldAlert, SignalHigh, Server, Database } from "lucide-react";

export function Header() {
  return (
    <header className="h-14 border-b border-border/50 bg-card/50 backdrop-blur-xl flex items-center justify-between px-6 z-50 shrink-0">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-primary" />
          <h1 className="font-bold tracking-tight text-foreground uppercase">
            NYC Food Policy <span className="text-muted-foreground font-normal">| Vulnerability Ops</span>
          </h1>
        </div>
        <div className="h-4 w-px bg-border mx-2" />
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[10px] font-mono font-medium text-emerald-400 uppercase tracking-wider">
            Live Feed Active
          </span>
        </div>
      </div>
      
      <div className="flex items-center gap-6 text-xs font-mono text-muted-foreground">
        <div className="flex items-center gap-2">
          <Server className="w-3.5 h-3.5" />
          <span>SYS.OP.OK</span>
        </div>
        <div className="flex items-center gap-2">
          <Database className="w-3.5 h-3.5" />
          <span>DATA.SYNC</span>
        </div>
        <div className="flex items-center gap-2">
          <SignalHigh className="w-3.5 h-3.5 text-primary" />
          <span>SECURE.LINK</span>
        </div>
      </div>
    </header>
  );
}
