import React from "react";
import { AlertTriangle } from "lucide-react";
import { IntegrationCard } from "./IntegrationCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export const IntegrationsSection = ({ isConnected = false }: { isConnected?: boolean }) => {
  const integrations = [
    {
      name: "QuickBooks Integration",
      description: (
        <span className="text-foreground font-medium">
          Stop manually entering invoices. LienDeadline reads your QuickBooks invoices and calculates all deadlines automatically.
        </span>
      ),
      icon: "Q",
      gradient: "bg-gradient-to-br from-blue-500 to-blue-600",
      onConnect: () => {
        const token = localStorage.getItem('session_token');
        if (token) {
          window.location.href = `/api/quickbooks/connect?token=${encodeURIComponent(token)}`;
        } else {
          window.location.href = '/login.html';
        }
      },
      connected: isConnected,
    },
    {
      name: "Sage Integration",
      description: "Import invoices from Sage accounting",
      icon: "S",
      gradient: "bg-gradient-to-br from-green-500 to-green-600",
    },
    {
      name: "Procore Integration",
      description: "Import projects and calculate lien deadlines",
      icon: "P",
      gradient: "bg-gradient-to-br from-orange-500 to-orange-600",
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {integrations.map((integration) => (
          <IntegrationCard
            key={integration.name}
            name={integration.name}
            description={integration.description}
            icon={integration.icon}
            gradient={integration.gradient}
            onConnect={integration.onConnect}
            connected={integration.connected}
          />
        ))}
      </div>
    </div>
  );
};
