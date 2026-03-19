import { useState } from "react";
import { Bot, Zap, Send, FileText, TrendingDown, Target, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";

export function RightPanel() {
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState([
    { role: "assistant", text: "NYC Food Policy AI initialized. I have analyzed the latest vulnerability metrics across all 59 community districts. How can I assist your operations today?" }
  ]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    
    setMessages(prev => [...prev, { role: "user", text: chatInput }]);
    setChatInput("");
    
    // Mock response
    setTimeout(() => {
      setMessages(prev => [...prev, { role: "assistant", text: "Running simulation... Federal SNAP cuts of 15% would disproportionately impact University Heights (CD 205) and Morrisania (CD 203), pushing an estimated 12,500 households into severe food insecurity within 30 days." }]);
    }, 1000);
  };

  return (
    <div className="w-96 flex-shrink-0 border-l border-border/50 bg-card/30 flex flex-col h-full backdrop-blur-sm z-10">
      
      {/* Alerts Section */}
      <div className="p-4 border-b border-border/50 shrink-0 bg-background/50">
        <h3 className="text-[10px] font-bold text-muted-foreground font-mono tracking-wider mb-3 flex items-center gap-2">
          <AlertCircle className="w-3 h-3 text-red-500" /> ACTIVE ALERTS
        </h3>
        <div className="space-y-2">
          <div className="bg-red-500/10 border border-red-500/20 p-2.5 rounded-lg flex gap-3 items-start">
            <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5 animate-pulse shrink-0" />
            <div>
              <p className="text-xs font-medium text-foreground">SNAP Funding Reduction</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">Title IV expiration expected to hit Bronx CDs hardest in 45 days.</p>
            </div>
          </div>
          <div className="bg-orange-500/10 border border-orange-500/20 p-2.5 rounded-lg flex gap-3 items-start">
            <div className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-foreground">Pantry Shortage: East NY</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">3 major pantries reported critical supply drops this week.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="p-4 border-b border-border/50 shrink-0 grid grid-cols-3 gap-2">
        <button className="flex flex-col items-center justify-center gap-2 p-3 rounded-lg bg-secondary hover:bg-primary/20 hover:text-primary border border-transparent hover:border-primary/50 transition-all text-muted-foreground">
          <FileText className="w-4 h-4" />
          <span className="text-[9px] font-bold text-center">GENERATE REPORT</span>
        </button>
        <button className="flex flex-col items-center justify-center gap-2 p-3 rounded-lg bg-secondary hover:bg-primary/20 hover:text-primary border border-transparent hover:border-primary/50 transition-all text-muted-foreground">
          <TrendingDown className="w-4 h-4" />
          <span className="text-[9px] font-bold text-center">SNAP IMPACT</span>
        </button>
        <button className="flex flex-col items-center justify-center gap-2 p-3 rounded-lg bg-secondary hover:bg-primary/20 hover:text-primary border border-transparent hover:border-primary/50 transition-all text-muted-foreground">
          <Target className="w-4 h-4" />
          <span className="text-[9px] font-bold text-center">PANTRY GAPS</span>
        </button>
      </div>

      {/* AI Assistant */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="p-3 border-b border-border/50 flex items-center gap-2 bg-primary/5">
          <Bot className="w-4 h-4 text-primary" />
          <span className="text-xs font-bold text-primary font-mono tracking-wide">FOOD POLICY AI (CLAUDE)</span>
          <span className="ml-auto flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
          </span>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans text-sm">
          {messages.map((msg, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              key={i} 
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
            >
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${msg.role === "user" ? "bg-secondary text-foreground" : "bg-primary/20 text-primary border border-primary/30"}`}>
                {msg.role === "user" ? <span className="text-[10px]">ME</span> : <Bot className="w-3.5 h-3.5" />}
              </div>
              <div className={`p-3 rounded-xl max-w-[85%] ${
                msg.role === "user" 
                  ? "bg-secondary text-foreground rounded-tr-none" 
                  : "bg-primary/10 border border-primary/20 text-foreground/90 rounded-tl-none leading-relaxed"
              }`}>
                {msg.text}
              </div>
            </motion.div>
          ))}
        </div>
        
        <div className="p-3 shrink-0 border-t border-border/50 bg-background/50">
          <form onSubmit={handleSend} className="relative">
            <input 
              type="text" 
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask about data or run scenarios..."
              className="w-full bg-card border border-border rounded-full pl-4 pr-10 py-2.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary text-foreground placeholder:text-muted-foreground"
            />
            <button 
              type="submit"
              disabled={!chatInput.trim()}
              className="absolute right-1 top-1 p-1.5 text-primary hover:bg-primary/20 rounded-full transition-colors disabled:opacity-50 disabled:hover:bg-transparent"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
