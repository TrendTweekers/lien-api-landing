import { useState, useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { IntegrationCard } from "./IntegrationCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const connectQuickBooks = () => {
  console.log('[Dashboard V2] Initiating QuickBooks OAuth flow...');
  
  // Constants
  const CLIENT_ID = 'ABemmZS0yvUoHIlL06pbq2DhnpX0zM0RDS7bBtNADNzYPq3xui';
  const REDIRECT_URI = `${window.location.origin}/api/quickbooks/callback`;
  const SCOPE = 'com.intuit.quickbooks.accounting';
  
  // Generate state for CSRF protection
  const state = Math.random().toString(36).substring(7);
  localStorage.setItem('qb_state', state);

  // Set state in cookie for backend validation
  document.cookie = `oauth_state=${state}; path=/; max-age=600; secure; samesite=lax`;
  
  // Also set session_token in cookie so backend can identify user during callback
  const sessionToken = localStorage.getItem('session_token');
  if (sessionToken) {
    document.cookie = `session_token=${sessionToken}; path=/; max-age=600; secure; samesite=lax`;
  }
  
  // Store return URL to redirect back to V2 after callback
  localStorage.setItem('qb_return_url', window.location.href);
  
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

export const IntegrationsSection = () => {
  const [isQBConnected, setIsQBConnected] = useState(false);

  useEffect(() => {
    const checkConnection = async () => {
      // Check for URL param first (immediate feedback after redirect)
      const params = new URLSearchParams(window.location.search);
      if (params.get('qb_connected') === 'true') {
        setIsQBConnected(true);
        return;
      }

      // Check backend status
      try {
        const token = localStorage.getItem('session_token');
        const headers: HeadersInit = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        
        // We can check if invoices endpoint returns 200 or 404
        // Or check a dedicated status endpoint if available.
        // For now, let's try the invoices endpoint as requested by user
        // "If the invoices array exists (even if empty), force the badge status to Connected"
        const res = await fetch("/api/quickbooks/invoices", { 
            method: 'HEAD',
            headers 
        });
        
        if (res.ok) {
            setIsQBConnected(true);
        }
      } catch (e) {
        console.error("Failed to check QB status", e);
      }
    };

    checkConnection();
  }, []);

  const integrations = [
    {
      name: "QuickBooks Integration",
      description: (
        <span className="text-foreground font-medium block min-h-[80px] pb-4">
          Stop manually entering invoices. LienDeadline reads your QuickBooks invoices and calculates all deadlines automatically.
        </span>
      ),
      icon: "Q",
      gradient: "bg-gradient-to-br from-blue-500 to-blue-600",
      onConnect: connectQuickBooks,
      connected: isQBConnected,
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
