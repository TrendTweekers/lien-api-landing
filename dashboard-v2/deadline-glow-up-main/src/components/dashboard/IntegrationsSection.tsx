import React, { useState, useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { IntegrationCard } from "./IntegrationCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";

export const IntegrationsSection = ({ isConnected = false }: { isConnected?: boolean }) => {
  const { toast } = useToast();
  const [connected, setConnected] = useState(isConnected);

  // Sync local state with prop changes
  useEffect(() => {
    console.log(`🔄 IntegrationsSection - isConnected prop changed:`, isConnected);
    setConnected(isConnected);
  }, [isConnected]);

  const handleDisconnect = async () => {
    try {
      const token = localStorage.getItem('session_token');
      if (!token) {
        toast({
          title: "Error",
          description: "Please log in to disconnect QuickBooks.",
          variant: "destructive",
        });
        return;
      }

      const response = await fetch("/api/quickbooks/disconnect", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to disconnect");
      }

      setConnected(false);
      toast({
        title: "Disconnected",
        description: "QuickBooks account has been disconnected.",
      });

      // Refresh the page to update the UI
      window.location.reload();
    } catch (error) {
      console.error("Error disconnecting QuickBooks:", error);
      toast({
        title: "Error",
        description: "Failed to disconnect QuickBooks. Please try again.",
        variant: "destructive",
      });
    }
  };

  const integrations = [
    {
      name: "QuickBooks Integration",
      description: "Import invoices and auto-calculate deadlines",
      icon: "QB",
      iconColor: "#0077C5", // Official Intuit blue
      onConnect: () => {
        const token = localStorage.getItem('session_token');
        if (token) {
          window.location.href = `/api/quickbooks/connect?token=${encodeURIComponent(token)}`;
        } else {
          window.location.href = '/login.html';
        }
      },
      onDisconnect: handleDisconnect,
      connected: connected,
    },
    {
      name: "Sage Integration",
      description: "Import invoices from Sage accounting",
      icon: "S",
      iconColor: "#00B140", // Sage brand green
    },
    {
      name: "Procore Integration",
      description: "Import projects and calculate deadlines",
      icon: "P",
      iconColor: "#F68D2E", // Procore brand orange
    },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-foreground">Accounting Integrations</h2>
      
      <Alert className="bg-warning/10 border-warning/40">
        <AlertTriangle className="h-5 w-5 text-warning" />
        <AlertTitle className="font-semibold text-foreground">Beta Feature</AlertTitle>
        <AlertDescription className="text-muted-foreground">
          Integrations are currently in beta testing. For now, we recommend manually entering invoice dates into the calculator above.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {integrations.map((integration) => (
          <IntegrationCard
            key={integration.name}
            name={integration.name}
            description={integration.description}
            icon={integration.icon}
            iconColor={integration.iconColor}
            gradient={integration.gradient}
            onConnect={integration.onConnect}
            onDisconnect={integration.onDisconnect}
            connected={integration.connected}
          />
        ))}
      </div>
    </div>
  );
};
