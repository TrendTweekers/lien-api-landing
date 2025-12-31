import { AlertTriangle } from "lucide-react";
import { IntegrationCard } from "./IntegrationCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const connectQuickBooks = () => {
  console.log('[Dashboard V2] Initiating QuickBooks OAuth flow...');
  
  // Constants
  const CLIENT_ID = 'ABemmZS0yvUoHIlL06pbq2DhnpX0zM0RDS7bBtNADNzYPq3xui';
  const REDIRECT_URI = 'https://liendeadline.com/api/quickbooks/callback';
  const SCOPE = 'com.intuit.quickbooks.accounting';
  
  // Generate state for CSRF protection
  const state = Math.random().toString(36).substring(7);
  localStorage.setItem('qb_state', state);
  
  // Construct OAuth URL
  const oauthUrl = `https://appcenter.intuit.com/connect/oauth2` +
      `?client_id=${CLIENT_ID}` +
      `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
      `&scope=${SCOPE}` +
      `&response_type=code` +
      `&state=${state}`;
      
  console.log('[Dashboard V2] Redirecting to:', oauthUrl);
  
  // Redirect
  window.location.href = oauthUrl;
};

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
    onConnect: connectQuickBooks,
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

export const IntegrationsSection = () => {
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
          />
        ))}
      </div>
    </div>
  );
};
