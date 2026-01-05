import React from "react";
import { useNavigate } from "react-router-dom";
import { Copy, Check, CheckCircle2, HelpCircle, Key, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

export const IntegrationsSection = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [webhookUrl, setWebhookUrl] = React.useState("");
  const [triggerUrl, setTriggerUrl] = React.useState("");
  const [copied, setCopied] = React.useState<string | null>(null);
  const [tokenStatus, setTokenStatus] = React.useState<{has_token: boolean; last4: string | null; created_at: string | null} | null>(null);
  const [showTokenDialog, setShowTokenDialog] = React.useState(false);
  const [newToken, setNewToken] = React.useState<string | null>(null);
  const [isLoadingToken, setIsLoadingToken] = React.useState(false);

  React.useEffect(() => {
    const baseUrl = window.location.origin;
    setWebhookUrl(`${baseUrl}/api/zapier/webhook/invoice`);
    setTriggerUrl(`${baseUrl}/api/zapier/trigger/upcoming?limit=10`);
    fetchTokenStatus();
  }, []);

  const fetchTokenStatus = async () => {
    try {
      const token = localStorage.getItem('session_token');
      if (!token) return;
      
      const response = await fetch('/api/zapier/token', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setTokenStatus(data);
      }
    } catch (error) {
      console.error('Error fetching token status:', error);
    }
  };

  const handleGenerateToken = async () => {
    setIsLoadingToken(true);
    try {
      const token = localStorage.getItem('session_token');
      if (!token) {
        toast({
          title: "Error",
          description: "Please log in to generate a token.",
          variant: "destructive",
        });
        return;
      }
      
      const response = await fetch('/api/zapier/token/regenerate', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setNewToken(data.token);
        setShowTokenDialog(true);
        fetchTokenStatus();
      } else {
        throw new Error('Failed to generate token');
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate token. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoadingToken(false);
    }
  };

  const handleRevokeToken = async () => {
    try {
      const token = localStorage.getItem('session_token');
      if (!token) return;
      
      const response = await fetch('/api/zapier/token/revoke', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        toast({
          title: "Success",
          description: "Zapier token revoked successfully.",
        });
        setTokenStatus({ has_token: false, last4: null, created_at: null });
      } else {
        throw new Error('Failed to revoke token');
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to revoke token. Please try again.",
        variant: "destructive",
      });
    }
  };

  const copyToClipboard = (text: string, type: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(type);
      toast({
        title: "Copied!",
        description: "URL copied to clipboard",
      });
      setTimeout(() => setCopied(null), 1500);
    });
  };

  const handleViewZaps = () => {
    navigate('/zapier');
  };

  // Get Started Stepper Component
  const GetStartedStepper = () => {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-foreground">Get started</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Step 1 */}
          <div className="bg-card rounded-lg p-4 border border-border">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
                1
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-foreground text-sm mb-1">Copy Webhook URL</h4>
                <p className="text-xs text-muted-foreground mb-2">
                  Use this in Zapier to send invoices to LienDeadline.
                </p>
                <div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={() => copyToClipboard(webhookUrl, "stepper-webhook")}
                  >
                    {copied === "stepper-webhook" ? (
                      <>
                        <Check className="h-3 w-3 mr-1" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" /> Copy Webhook
                      </>
                    )}
                  </Button>
                  {copied === "stepper-webhook" && (
                    <p className="text-xs text-muted-foreground mt-1">Copied ✅</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Step 2 */}
          <div className="bg-card rounded-lg p-4 border border-border">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
                2
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-foreground text-sm mb-1">Copy Trigger URL</h4>
                <p className="text-xs text-muted-foreground mb-2">
                  Use this in Zapier to pull upcoming deadlines.
                </p>
                <div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={() => copyToClipboard(triggerUrl, "stepper-trigger")}
                  >
                    {copied === "stepper-trigger" ? (
                      <>
                        <Check className="h-3 w-3 mr-1" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" /> Copy Trigger
                      </>
                    )}
                  </Button>
                  {copied === "stepper-trigger" && (
                    <p className="text-xs text-muted-foreground mt-1">Copied ✅</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Step 3 */}
          <div className="bg-card rounded-lg p-4 border border-border">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
                3
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-foreground text-sm mb-1">Choose a Zap template</h4>
                <p className="text-xs text-muted-foreground mb-2">
                  Browse pre-built workflows to get started quickly.
                </p>
                <Button
                  size="sm"
                  className="h-7 text-xs bg-orange-600 hover:bg-orange-700 text-white"
                  onClick={handleViewZaps}
                >
                  View Popular Zaps
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Zapier Card Component
  const ZapierCard = () => {

    return (
      <div className="bg-card rounded-xl p-4 md:p-6 border-2 border-primary/30 hover:shadow-xl hover:border-primary/50 transition-all duration-300 card-shadow group w-full max-w-none flex flex-col ring-1 ring-primary/10">
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
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground border border-border">
                6,000+ apps
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
            Works with 6,000+ apps. Automatically create projects from invoices and get notified about upcoming deadlines.
          </p>
        </div>

        {/* Zapier API Token Section */}
        <div className="mb-4 p-3 bg-muted/30 rounded-lg border border-border">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div className="flex items-center gap-2">
              <Key className="h-4 w-4 text-muted-foreground" />
              <Label className="text-xs font-medium">Zapier API Token</Label>
              {tokenStatus?.has_token && (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs"
                  onClick={handleGenerateToken}
                  disabled={isLoadingToken}
                >
                  {isLoadingToken ? "Generating..." : "Regenerate"}
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              {tokenStatus?.has_token ? (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={handleRevokeToken}
                  >
                    Revoke
                  </Button>
                  <Badge variant="secondary" className="text-xs">
                    Active (••••{tokenStatus.last4})
                  </Badge>
                </>
              ) : (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={handleGenerateToken}
                    disabled={isLoadingToken}
                  >
                    {isLoadingToken ? "Generating..." : "Generate Token"}
                  </Button>
                  <Badge variant="outline" className="text-xs">
                    Not created
                  </Badge>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4 mb-4">
          <div>
            <Label className="text-xs font-medium mb-1 block">Webhook URL</Label>
            <div className="flex gap-2 w-full">
              <Input
                type="text"
                value={webhookUrl}
                readOnly
                className="flex-1 text-xs font-mono h-9"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-9 px-3 shrink-0"
                onClick={() => copyToClipboard(webhookUrl, "webhook")}
              >
                {copied === "webhook" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          <div>
            <Label className="text-xs font-medium mb-1 block">Trigger URL</Label>
            <div className="flex gap-2 w-full">
              <Input
                type="text"
                value={triggerUrl}
                readOnly
                className="flex-1 text-xs font-mono h-9"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-9 px-3 shrink-0"
                onClick={() => copyToClipboard(triggerUrl, "trigger")}
              >
                {copied === "trigger" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-auto">
          <Button
            className="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium"
            size="sm"
            onClick={handleViewZaps}
          >
            🔗 View Popular Zaps
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 w-full">
      <h2 className="text-xl font-semibold text-foreground">Accounting Integrations</h2>
      
      <Alert className="bg-primary/10 border-primary/30">
        <CheckCircle2 className="h-5 w-5 text-primary" />
        <AlertTitle className="font-semibold text-foreground">Connect via Zapier in 3 minutes</AlertTitle>
        <AlertDescription className="text-muted-foreground space-y-2">
          <p>Send invoices from any tool → LienDeadline calculates deadlines → get alerts anywhere.</p>
          <ul className="list-disc list-inside space-y-1 text-sm mt-2">
            <li>Import invoices from any system</li>
            <li>Auto-calculate notice + lien deadlines</li>
            <li>Send alerts to Slack/Email/Asana/CRM</li>
          </ul>
          <div className="mt-3 pt-2 border-t border-primary/20">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-primary hover:text-primary hover:bg-primary/10"
              onClick={() => navigate('/help/zapier')}
            >
              <HelpCircle className="h-3 w-3 mr-1" />
              Need help setting up Zapier?
            </Button>
          </div>
        </AlertDescription>
      </Alert>

      <GetStartedStepper />

      {/* Zapier Card - Full width, same as Get Started section */}
      <div className="w-full max-w-none">
        <ZapierCard />
      </div>

      {/* Token Dialog */}
      <Dialog open={showTokenDialog} onOpenChange={setShowTokenDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Zapier API Token</DialogTitle>
            <DialogDescription>
              Copy this token now — you won't see it again.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium mb-2 block">Your Zapier API Token</Label>
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={newToken || ""}
                  readOnly
                  className="flex-1 font-mono text-sm"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (newToken) {
                      copyToClipboard(newToken, "new-token");
                    }
                  }}
                >
                  {copied === "new-token" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            {newToken && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <code className="text-xs font-mono bg-muted px-2 py-1 rounded flex-1">
                    Authorization: Bearer {newToken}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={() => {
                      if (newToken) {
                        copyToClipboard(`Authorization: Bearer ${newToken}`, "header");
                      }
                    }}
                  >
                    {copied === "header" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                    Copy header
                  </Button>
                </div>
              </div>
            )}
            <Alert className="bg-warning/10 border-warning/30">
              <AlertDescription className="text-xs">
                Store this token securely. Use it in Zapier webhook headers as: <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;token&gt;</code>
              </AlertDescription>
            </Alert>
            <div className="flex justify-end">
              <Button onClick={() => setShowTokenDialog(false)}>Done</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
