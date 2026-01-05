import React, { useState, useEffect } from "react";
import { AlertTriangle, Copy, Check } from "lucide-react";
import { IntegrationCard } from "./IntegrationCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
      name: "QuickBooks Integration (Optional)",
      description: "Direct QuickBooks integration for existing QuickBooks users",
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

  // Zapier Card Component
  const ZapierCard = () => {
    const [webhookUrl, setWebhookUrl] = React.useState("");
    const [triggerUrl, setTriggerUrl] = React.useState("");
    const [copied, setCopied] = React.useState<string | null>(null);

    React.useEffect(() => {
      const baseUrl = window.location.origin;
      setWebhookUrl(`${baseUrl}/api/zapier/webhook/invoice`);
      setTriggerUrl(`${baseUrl}/api/zapier/trigger/upcoming?limit=10`);
    }, []);

    const copyToClipboard = (text: string, type: string) => {
      navigator.clipboard.writeText(text).then(() => {
        setCopied(type);
        toast({
          title: "Copied!",
          description: "URL copied to clipboard",
        });
        setTimeout(() => setCopied(null), 2000);
      });
    };

    return (
      <div className="bg-card rounded-xl p-6 border-2 border-primary/30 hover:shadow-xl hover:border-primary/50 transition-all duration-300 card-shadow group h-full flex flex-col ring-1 ring-primary/10">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-14 h-14 rounded-xl flex items-center justify-center text-white font-bold text-base shrink-0 bg-gradient-to-br from-orange-500 to-orange-600">
            <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 22C6.486 22 2 17.514 2 12S6.486 2 12 2s10 4.486 10 10-4.486 10-10 10zm-1-11V7h2v4h4v2h-4v4h-2v-4H7v-2h4z"/>
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors text-base">
                Zapier (Recommended)
              </h3>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                Primary
              </span>
            </div>
            <div className="text-sm text-muted-foreground leading-relaxed mb-1">
              Import invoices from ANY system via Zapier
            </div>
            <div className="text-xs text-muted-foreground italic">
              Turn invoices from any system into lien deadlines automatically.
            </div>
          </div>
        </div>

        <div className="mb-4">
          <p className="text-xs text-muted-foreground mb-3">
            Connect with 6,000+ apps including QuickBooks, Sage, Procore, and more. Automatically create projects from invoices and get notified about upcoming deadlines.
          </p>
        </div>

        <div className="space-y-3 mb-4">
          <div>
            <Label className="text-xs font-medium mb-1 block">Webhook URL</Label>
            <div className="flex gap-1">
              <Input
                type="text"
                value={webhookUrl}
                readOnly
                className="flex-1 text-xs font-mono h-8"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-2"
                onClick={() => copyToClipboard(webhookUrl, "webhook")}
              >
                {copied === "webhook" ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          </div>

          <div>
            <Label className="text-xs font-medium mb-1 block">Trigger URL</Label>
            <div className="flex gap-1">
              <Input
                type="text"
                value={triggerUrl}
                readOnly
                className="flex-1 text-xs font-mono h-8"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-2"
                onClick={() => copyToClipboard(triggerUrl, "trigger")}
              >
                {copied === "trigger" ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-auto">
          <Button
            className="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium"
            size="sm"
            onClick={() => window.open("https://zapier.com/apps/liendeadline/integrations", "_blank")}
          >
            🔗 View Popular Zaps
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-foreground">Accounting Integrations</h2>
      
      <Alert className="bg-primary/10 border-primary/30">
        <AlertTriangle className="h-5 w-5 text-primary" />
        <AlertTitle className="font-semibold text-foreground">Recommended: Zapier Integration</AlertTitle>
        <AlertDescription className="text-muted-foreground">
          Connect Zapier to import invoices from any accounting system (QuickBooks, Sage, Procore, and 6,000+ more apps). Automatic deadline calculation and alerts included.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <ZapierCard />
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
