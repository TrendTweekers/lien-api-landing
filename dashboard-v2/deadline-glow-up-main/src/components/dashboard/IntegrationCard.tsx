import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, MoreVertical } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface IntegrationCardProps {
  name: string;
  description: string | React.ReactNode;
  icon: string;
  iconColor?: string;
  gradient?: string;
  connected?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export const IntegrationCard = ({
  name,
  description,
  icon,
  iconColor,
  gradient,
  connected = false,
  onConnect,
  onDisconnect,
}: IntegrationCardProps) => {
  // Debug logging for connection status
  if (name === "QuickBooks Integration") {
    console.log(`🔍 QuickBooks Integration Card - connected prop:`, connected);
  }

  // Use brand color if provided, otherwise fall back to gradient
  const iconBgStyle = iconColor 
    ? { backgroundColor: iconColor }
    : undefined;
  const iconBgClass = iconColor 
    ? "" 
    : (gradient || "bg-gradient-to-br from-gray-500 to-gray-600");

  return (
    <div className="bg-card rounded-xl p-6 border border-border hover:shadow-lg transition-shadow duration-200 card-shadow group h-full flex flex-col">
      <div className="flex items-start gap-4 mb-4">
        <div
          className={`w-14 h-14 rounded-xl flex items-center justify-center text-white font-bold text-base shrink-0 ${iconBgClass}`}
          style={iconBgStyle}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors text-base mb-2">
            {name}
          </h3>
          <div className="text-sm text-muted-foreground leading-relaxed">
            {description}
          </div>
        </div>
      </div>

      <div className="mt-auto pt-4 flex items-center justify-between border-t border-border">
        <Badge
          variant={connected ? "default" : "secondary"}
          className={
            connected 
              ? "bg-[#10B981] text-white border-[#10B981] rounded-md px-2.5 py-0.5 text-xs font-medium" 
              : "bg-muted text-muted-foreground rounded-md px-2.5 py-0.5 text-xs font-medium"
          }
        >
          {connected ? "Connected" : "Not connected"}
        </Badge>
      </div>

      <div className="mt-4 space-y-2">
        {name === "QuickBooks Integration" ? (
          <>
            {connected ? (
              // When connected: Show Manage dropdown menu (no Connect button)
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    className="w-full border-border hover:bg-muted transition-all duration-200"
                    size="sm"
                  >
                    <MoreVertical className="h-4 w-4 mr-2" />
                    Manage
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={onDisconnect}
                    className="text-destructive focus:text-destructive cursor-pointer"
                  >
                    Disconnect QuickBooks
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              // When not connected: Show official Intuit Connect button image
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  const token = localStorage.getItem('session_token');
                  if (token) {
                    window.location.href = `/api/quickbooks/connect?token=${encodeURIComponent(token)}`;
                  } else {
                    window.location.href = '/login.html';
                  }
                }}
                className="w-full inline-flex items-center justify-center cursor-pointer hover:opacity-90 transition-opacity"
                style={{ textDecoration: 'none' }}
              >
                <img
                  src="https://developer.intuit.com/static/images/buttons/connect-to-quickbooks.png"
                  alt="Connect to QuickBooks"
                  className="w-full h-auto"
                  style={{ maxWidth: '100%', height: 'auto', display: 'block' }}
                  onError={(e) => {
                    // Fallback: If image fails to load, show styled button
                    const target = e.target as HTMLImageElement;
                    target.style.display = 'none';
                    const parent = target.parentElement;
                    if (parent && !parent.querySelector('.fallback-btn')) {
                      const fallback = document.createElement('button');
                      fallback.className = 'fallback-btn w-full inline-flex items-center justify-center rounded-md text-sm font-medium transition-all duration-200 bg-[#0077C5] text-white hover:bg-[#0066A3] hover:shadow-md h-9 px-4';
                      fallback.textContent = 'Connect to QuickBooks';
                      fallback.onclick = (ev) => {
                        ev.preventDefault();
                        const token = localStorage.getItem('session_token');
                        if (token) {
                          window.location.href = `/api/quickbooks/connect?token=${encodeURIComponent(token)}`;
                        } else {
                          window.location.href = '/login.html';
                        }
                      };
                      parent.appendChild(fallback);
                    }
                  }}
                />
              </a>
            )}
          </>
        ) : (
          <Button
            className="w-full bg-primary hover:bg-primary/90 hover:shadow-md transition-all duration-200 text-primary-foreground font-medium"
            size="sm"
            onClick={onConnect}
          >
            {connected ? "Manage" : `Connect ${name.split(" ")[0]}`}
          </Button>
        )}

        <button className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1 py-1">
          <AlertCircle className="h-3 w-3" />
          Report Issue
        </button>
      </div>
    </div>
  );
};
