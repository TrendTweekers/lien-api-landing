import React from "react";
import { Copy, Check, CheckCircle2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const IntegrationsSection = () => {
  const { toast } = useToast();
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
      setTimeout(() => setCopied(null), 1500);
    });
  };

  const handleViewZaps = () => {
    window.open("https://zapier.com/apps/liendeadline/integrations", "_blank");
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
            onClick={handleViewZaps}
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
        <CheckCircle2 className="h-5 w-5 text-primary" />
        <AlertTitle className="font-semibold text-foreground">Connect via Zapier in 3 minutes</AlertTitle>
        <AlertDescription className="text-muted-foreground space-y-2">
          <p>Send invoices from any tool → LienDeadline calculates deadlines → get alerts anywhere.</p>
          <ul className="list-disc list-inside space-y-1 text-sm mt-2">
            <li>Import invoices from any system</li>
            <li>Auto-calculate notice + lien deadlines</li>
            <li>Send alerts to Slack/Email/Asana/CRM</li>
          </ul>
        </AlertDescription>
      </Alert>

      <GetStartedStepper />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
        <ZapierCard />
      </div>
    </div>
  );
};
