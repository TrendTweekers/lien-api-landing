import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle } from "lucide-react";

interface IntegrationCardProps {
  name: string;
  description: string | React.ReactNode;
  icon: React.ReactNode;
  gradient: string;
  connected?: boolean;
  onConnect?: () => void;
}

export const IntegrationCard = ({
  name,
  description,
  icon,
  gradient,
  connected = false,
  onConnect,
}: IntegrationCardProps) => {
  return (
    <div className="bg-card rounded-xl p-6 border border-border hover-lift card-shadow group">
      <div className="flex items-start gap-4">
        <div
          className={`w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg shrink-0 ${gradient}`}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
            {name}
          </h3>
          <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
            {description}
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <Badge
          variant={connected ? "default" : "secondary"}
          className={connected ? "bg-success/20 text-success border-success/30" : "bg-muted text-muted-foreground"}
        >
          {connected ? "Connected" : "Not connected"}
        </Badge>
      </div>

      {name === "QuickBooks Integration" ? (
        <button
          onClick={() => {
            const token = localStorage.getItem('session_token');
            if (token) {
              window.location.href = `/api/quickbooks/connect?token=${encodeURIComponent(token)}`;
            } else {
              window.location.href = '/login.html';
            }
          }}
          className="w-full inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-3 mt-4"
        >
          {connected ? "Manage" : "Connect QuickBooks"}
        </button>
      ) : (
        <Button
          className="w-full mt-4 bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
          size="sm"
          onClick={onConnect}
        >
          {connected ? "Manage" : `Connect ${name.split(" ")[0]}`}
        </Button>
      )}

      <button className="w-full mt-2 text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1">
        <AlertCircle className="h-3 w-3" />
        Report Issue
      </button>
    </div>
  );
};
