import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Copy, Check, HelpCircle } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";

const ZapierHelp = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [webhookUrl, setWebhookUrl] = useState("");
  const [triggerUrl, setTriggerUrl] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    // Check for session token and verify session
    const token = localStorage.getItem('session_token');
    if (!token) {
      window.location.href = '/login.html';
      return;
    }
    
    fetch('/api/verify-session', {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(res => {
      if (!res.ok) {
        window.location.href = '/login.html';
      }
    }).catch(() => {
      window.location.href = '/login.html';
    });

    // Set URLs
    const baseUrl = window.location.origin;
    setWebhookUrl(`${baseUrl}/api/zapier/webhook/invoice`);
    setTriggerUrl(`${baseUrl}/api/zapier/trigger/upcoming?limit=10`);
  }, []);

  const copyToClipboard = (text: string, type: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(type);
      toast({
        title: "Copied!",
        description: "Copied to clipboard",
      });
      setTimeout(() => setCopied(null), 1500);
    });
  };

  const webhookExample = {
    project_name: "Ironclad Construction Partners - 1001",
    client_name: "Ironclad Construction Partners",
    state: "CA",
    invoice_date: "2025-12-31",
    invoice_amount_cents: 499200,
    invoice_number: "1001"
  };

  const examples = [
    {
      title: "Slack alert",
      description: "Send deadline alerts to your team Slack channel when invoices are processed."
    },
    {
      title: "Asana/Trello task",
      description: "Create a task in your project management tool when deadlines are within 30 days."
    },
    {
      title: "Email escalation",
      description: "Send urgent email notifications when deadlines are within 10 days."
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />
      
      <main className="container py-8 max-w-4xl">
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Dashboard
            </Button>
          </div>

          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Zapier Setup (2 minutes)</h1>
            <p className="text-muted-foreground">
              Send invoices from any system → LienDeadline calculates deadlines → get alerts anywhere.
            </p>
          </div>

          {/* Zapier API v1 Info */}
          <Card className="bg-primary/5 border-primary/20">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                Zapier API v1 (Stable)
                <Badge variant="secondary" className="text-xs">v1</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>
                <span className="font-medium">Auth header:</span>{" "}
                <code className="bg-muted px-1 rounded text-xs">Authorization: Bearer &lt;zapier_token&gt;</code>
              </div>
              <div>
                <span className="font-medium">Webhook endpoint:</span>{" "}
                <code className="bg-muted px-1 rounded text-xs">POST /api/zapier/webhook/invoice</code>
              </div>
              <div>
                <span className="font-medium">Trigger endpoint:</span>{" "}
                <code className="bg-muted px-1 rounded text-xs">GET /api/zapier/trigger/upcoming?limit=10</code>
              </div>
              <div>
                <span className="font-medium">Required fields:</span>{" "}
                <code className="bg-muted px-1 rounded text-xs">state, invoice_date, invoice_amount_cents</code>
              </div>
              <p className="text-xs text-muted-foreground mt-2 italic">
                Breaking changes will only be introduced under a new version.
              </p>
            </CardContent>
          </Card>

          {/* Step 1: Webhook POST */}
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Step 1 — Send invoices to LienDeadline (Webhook POST)</CardTitle>
              <CardDescription>
                Configure Zapier to send invoice data to LienDeadline when invoices are created in your system.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Webhook URL */}
              <div>
                <label className="text-sm font-medium mb-2 block">Webhook URL</label>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono text-xs overflow-x-auto">
                    {webhookUrl}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(webhookUrl, "webhook")}
                  >
                    {copied === "webhook" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Zapier Steps */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground">Zapier Setup Steps:</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
                  <li>
                    <span className="font-medium text-foreground">Trigger:</span> Choose your source app (QuickBooks, Xero, Sage, Procore, Email Parser, Google Sheets, etc.) and select the "New Invoice" or equivalent event.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Action:</span> Add "Webhooks by Zapier" → Select "Custom Request"
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Method:</span> Select <code className="bg-muted px-1 rounded">POST</code>
                  </li>
                  <li>
                    <span className="font-medium text-foreground">URL:</span> Paste the Webhook URL above
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Data:</span> Paste the JSON body example below
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Headers:</span> Add <code className="bg-muted px-1 rounded">Content-Type: application/json</code>
                  </li>
                </ol>
              </div>

              {/* Webhook JSON Example */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Webhook JSON Example</label>
                </div>
                <p className="text-xs text-muted-foreground mb-2">
                  Required: state, invoice_date. Recommended: invoice_amount_cents, invoice_number. Optional: project_name, client_name.
                </p>
                <div className="bg-muted/30 rounded-md p-3 text-xs">
                  <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(webhookExample, null, 2)}
                  </pre>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs px-2 mt-2"
                    onClick={() => copyToClipboard(JSON.stringify(webhookExample, null, 2), "webhook-json")}
                  >
                    {copied === "webhook-json" ? (
                      <>
                        <Check className="h-3 w-3 mr-1" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" /> Copy JSON
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Step 2: Trigger GET */}
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Step 2 — Pull upcoming deadlines (Trigger GET)</CardTitle>
              <CardDescription>
                Set up a Zapier trigger to poll for projects with upcoming lien deadlines.
                <span className="block mt-1 text-xs text-muted-foreground">
                  For notifications, use <code className="bg-muted px-1 rounded">/trigger/reminders</code> (recommended). <code className="bg-muted px-1 rounded">/trigger/upcoming</code> is for dashboards/reports.
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Trigger URL */}
              <div>
                <label className="text-sm font-medium mb-2 block">Trigger URL</label>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono text-xs overflow-x-auto">
                    {triggerUrl}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(triggerUrl, "trigger")}
                  >
                    {copied === "trigger" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Zapier Steps */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground">Zapier Setup Steps:</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
                  <li>
                    <span className="font-medium text-foreground">Trigger:</span> Add "Webhooks by Zapier" → Select "GET"
                  </li>
                  <li>
                    <span className="font-medium text-foreground">URL:</span> Paste the Trigger URL above
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Authentication:</span> Add header: <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;your Zapier API token&gt;</code>
                    <Alert className="mt-2 bg-primary/10 border-primary/30">
                      <AlertDescription className="text-xs">
                        Generate your Zapier API token from the Integrations page. This token is stable and won't expire like session tokens. Session tokens still work for backwards compatibility, but Zapier tokens are recommended.
                      </AlertDescription>
                    </Alert>
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Filtering:</span> You can filter results using <code className="bg-muted px-1 rounded">prelim_deadline_days</code> or <code className="bg-muted px-1 rounded">lien_deadline_days</code> fields in Zapier's filter step.
                  </li>
                </ol>
              </div>
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Notifications & Reminders</CardTitle>
              <CardDescription>
                Best practices for setting up deadline reminders and notifications.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border border-border bg-muted/30 p-4">
                <h4 className="text-sm font-semibold text-foreground">What this does</h4>
                <p className="mt-1 text-sm text-muted-foreground">
                  Run a Zap on a schedule (hourly) → LienDeadline returns reminders due today (e.g. 7 days before, 1 day before) → Zapier sends them to Slack/Email/Asana.
                  Each reminder is returned <span className="font-medium text-foreground">once</span> (no duplicates), even if your Zap runs every hour.
                </p>
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-foreground">3-step setup (recommended)</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
                  <li>
                    <span className="font-medium text-foreground">Trigger:</span> Use{" "}
                    <span className="font-medium text-foreground">Schedule by Zapier</span>{" "}
                    → <span className="font-medium text-foreground">Every Hour</span>
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Action:</span> Webhooks by Zapier →{" "}
                    <span className="font-medium text-foreground">GET</span>
                    <div className="mt-2 flex items-center gap-2">
                      <code className="flex-1 px-3 py-2 bg-muted rounded-md text-xs font-mono overflow-x-auto">
                        {window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50
                      </code>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          copyToClipboard(
                            `${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`,
                            "reminders-url"
                          )
                        }
                      >
                        {copied === "reminders-url" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </Button>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Add header:{" "}
                      <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;your_zapier_token&gt;</code>
                    </div>
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Notify:</span> Send the reminder to Slack / Email / Asana (any app).
                    Zapier will process each reminder in the list.
                  </li>
                </ol>
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-foreground">Recommended offsets</h4>
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-2">
                  <li><span className="font-medium text-foreground">7 days</span> = early warning</li>
                  <li><span className="font-medium text-foreground">1 day</span> = final reminder</li>
                  <li>
                    Custom: <code className="bg-muted px-1 rounded">?days=1,3,7</code>
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-border bg-muted/30 p-4">
                <h4 className="text-sm font-semibold text-foreground">Fields you can use in your notification</h4>
                <p className="mt-1 text-sm text-muted-foreground">
                  Each reminder includes:
                  <code className="bg-muted px-1 rounded ml-1">reminder_type</code>,{" "}
                  <code className="bg-muted px-1 rounded">reminder_days</code>,{" "}
                  <code className="bg-muted px-1 rounded">deadline_date</code>, and full{" "}
                  <code className="bg-muted px-1 rounded">project</code> details (state, dates, amount).
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Common Examples */}
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Common Examples</CardTitle>
              <CardDescription>
                Popular workflows you can build with these endpoints.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {examples.map((example, idx) => (
                  <div key={idx} className="bg-muted/30 rounded-lg p-4 border border-border">
                    <h4 className="font-medium text-foreground text-sm mb-1">{example.title}</h4>
                    <p className="text-xs text-muted-foreground">{example.description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Footer CTA */}
          <div className="flex items-center justify-center gap-4 pt-4">
            <Button
              variant="outline"
              onClick={() => navigate('/zapier')}
            >
              View Popular Zaps
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/')}
            >
              Back to Integrations
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ZapierHelp;

