import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Copy, Check, ExternalLink } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const PopularZaps = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [webhookUrl, setWebhookUrl] = useState("");
  const [triggerUrl, setTriggerUrl] = useState("");
  const [remindersUrl, setRemindersUrl] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  
  // Headers template (user needs to replace YOUR_ZAPIER_TOKEN with their actual token)
  const headersTemplate = {
    "Authorization": "Bearer YOUR_ZAPIER_TOKEN",
    "Content-Type": "application/json"
  };
  
  // Headers template for reminders (with placeholder)
  const remindersHeadersTemplate = {
    "Authorization": "Bearer PASTE_YOUR_ZAPIER_TOKEN_HERE",
    "Content-Type": "application/json"
  };
  
  // Example JSON body for webhook
  const exampleJsonBody = {
    "state": "TX",
    "invoice_date": "2025-12-31",
    "invoice_amount_cents": 4992,
    "project_name": "Test Invoice"
  };
  
  // Slack message template (updated for reminders endpoint structure)
  const slackMessageTemplate = "🚨 {{project.project_name}} ({{project.state_code}}) — {{reminder_type}} deadline in {{reminder_days}} day(s)\nDeadline: {{deadline_date}}\nLien: {{project.lien_deadline}} ({{project.lien_deadline_days}} days)\nPrelim: {{project.prelim_deadline}} ({{project.prelim_deadline_days}} days)\nAmount: ${{project.invoice_amount}}";
  
  // New Slack message template for reminders card
  const remindersSlackMessageTemplate = "🚨 LienDeadline reminder: {{reminder_type}} deadline in {{reminder_days}} day(s)\nDeadline: {{deadline_date}}\nProject: {{project.project_name}} ({{project.state_code}})\nInvoice: {{project.invoice_date}} — ${{project.invoice_amount}}\nPrelim: {{project.prelim_deadline}} ({{project.prelim_deadline_days}}d)\nLien: {{project.lien_deadline}} ({{project.lien_deadline_days}}d)";
  
  // Zap setup steps for reminders (URL will be replaced dynamically)
  const getRemindersZapSetupSteps = (baseUrl: string) => `1) Trigger: Schedule by Zapier → Every Hour
2) Action: Webhooks by Zapier → GET
   URL: ${baseUrl}/api/zapier/trigger/reminders?days=1,7&limit=50
   Header: Authorization: Bearer <token>
3) Action: Slack → Send Channel Message (use template)`;

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
    setRemindersUrl(`${baseUrl}/api/zapier/trigger/reminders?days=1,7&limit=50`);
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

  // Build zapTemplates array dynamically to use state variables
  const buildZapTemplates = () => {
    const baseUrl = window.location.origin;
    const remindersUrlValue = remindersUrl || `${baseUrl}/api/zapier/trigger/reminders?days=1,7&limit=50`;
    
    return [
      {
        id: 0,
        title: "Deadline reminders → Slack (1 & 7 days)",
        description: "Run hourly. Sends Slack alerts when deadlines are approaching (deduplicated).",
        type: "reminders",
        remindersUrl: remindersUrlValue,
        headers: remindersHeadersTemplate,
        slackMessage: remindersSlackMessageTemplate,
        zapSteps: `1) Trigger: Schedule by Zapier → Every Hour
2) Action: Webhooks by Zapier → GET
   URL: ${baseUrl}/api/zapier/trigger/reminders?days=1,7&limit=50
   Header: Authorization: Bearer <token>
3) Action: Slack → Send Channel Message (use template)`
      },
    {
      id: 1,
      title: "Invoices → Lien deadlines → Slack alert",
      description: "Automatically calculate lien deadlines when invoices are created and alert your team in Slack.",
      trigger: {
        app: "Your Accounting System",
        event: "New invoice created"
      },
      actions: [
        {
          type: "webhook",
          app: "LienDeadline",
          description: "Webhook POST to LienDeadline",
          url: webhookUrl
        },
        {
          type: "slack",
          app: "Slack",
          description: "Send channel message"
        }
      ],
      webhookExample: {
        project_name: "Ironclad Construction Partners - 1001",
        client_name: "Ironclad Construction Partners",
        state: "CA",
        invoice_date: "2025-12-31",
        invoice_amount_cents: 499200,
        invoice_number: "1001"
      },
      fieldMapping: {
        webhook: {
          invoice_date: "Invoice date (YYYY-MM-DD)",
          state: "State code (e.g., TX, CA)",
          project_name: "Project name (optional)",
          client_name: "Client name (optional)",
          invoice_amount: "Invoice amount (optional)"
        },
        response: {
          project_name: "Project name",
          client_name: "Client name",
          invoice_amount: "Formatted amount (e.g., '4992.00')",
          invoice_amount_cents: "Amount in cents (e.g., 499200)",
          prelim_deadline: "Preliminary notice deadline (YYYY-MM-DD)",
          prelim_deadline_days: "Days until prelim deadline",
          lien_deadline: "Lien filing deadline (YYYY-MM-DD)",
          lien_deadline_days: "Days until lien deadline"
        }
      }
    },
    {
      id: 2,
      title: "Deadline within 30 days → Create Asana/Trello task",
      description: "Create a task in your project management tool when a lien deadline is approaching.",
      trigger: {
        app: "LienDeadline",
        event: "Upcoming deadline trigger"
      },
      actions: [
        {
          type: "trigger",
          app: "LienDeadline",
          description: "GET trigger for upcoming deadlines",
          url: triggerUrl
        },
        {
          type: "task",
          app: "Asana / Trello",
          description: "Create task"
        }
      ],
      fieldMapping: {
        trigger: {
          limit: "Number of results (default: 10)"
        },
        response: {
          projects: "Array of projects with upcoming deadlines",
          project_name: "Project name",
          lien_deadline: "Lien deadline (YYYY-MM-DD)",
          lien_deadline_days: "Days remaining"
        }
      }
    },
    {
      id: 3,
      title: "Deadline within 10 days → Email escalation",
      description: "Send an urgent email notification when a deadline is within 10 days.",
      trigger: {
        app: "LienDeadline",
        event: "Upcoming deadline trigger"
      },
      actions: [
        {
          type: "trigger",
          app: "LienDeadline",
          description: "GET trigger for upcoming deadlines",
          url: triggerUrl
        },
        {
          type: "email",
          app: "Gmail / Email",
          description: "Send email"
        }
      ],
      fieldMapping: {
        filter: {
          lien_deadline_days: "Filter where <= 10"
        },
        response: {
          project_name: "Project name",
          client_name: "Client name",
          lien_deadline: "Deadline date",
          lien_deadline_days: "Days remaining"
        }
      }
    },
    {
      id: 4,
      title: "Invoice created → Google Sheet row (audit log)",
      description: "Log all invoice calculations to a Google Sheet for audit and reporting.",
      trigger: {
        app: "Your Accounting System",
        event: "New invoice created"
      },
      actions: [
        {
          type: "webhook",
          app: "LienDeadline",
          description: "Webhook POST to LienDeadline",
          url: webhookUrl
        },
        {
          type: "sheet",
          app: "Google Sheets",
          description: "Add row to spreadsheet"
        }
      ],
      webhookExample: {
        project_name: "Downtown Office Renovation",
        client_name: "ABC Properties LLC",
        state: "TX",
        invoice_date: "2025-01-15",
        invoice_amount_cents: 1250000,
        invoice_number: "INV-2025-001"
      },
      fieldMapping: {
        webhook: {
          invoice_date: "Invoice date",
          state: "State code",
          project_name: "Project name",
          client_name: "Client name",
          invoice_amount: "Invoice amount"
        },
        response: {
          id: "Project ID",
          project_name: "Project name",
          invoice_date: "Invoice date",
          state: "State code",
          prelim_deadline: "Prelim deadline",
          lien_deadline: "Lien deadline",
          lien_deadline_days: "Days remaining"
        }
      }
    }
    ];
  };
  
  const zapTemplates = buildZapTemplates();

  return (
    <>
      <div style={{ background: 'red', color: 'white', padding: 8 }}>
        BUILD_STAMP_REMINDERS_V1
      </div>
      <div className="min-h-screen bg-background">
        <DashboardHeader />
      
      <main className="container py-8">
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
            <div className="flex items-center gap-2 mb-2">
              <h1 className="text-3xl font-bold text-foreground">Popular Zaps</h1>
              <Badge variant="secondary" className="text-xs">BUILD_STAMP: REMINDERS_CARD_V1</Badge>
            </div>
            <p className="text-muted-foreground">Pick a template. Build it in Zapier in minutes.</p>
          </div>

          {/* REMINDERS Section */}
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-foreground mb-1">REMINDERS</h2>
            <p className="text-sm text-muted-foreground">Run on a schedule. Sends alerts when deadlines are approaching.</p>
          </div>

          {/* Deadline Reminders → Slack Card (NEW - Top) */}
          <Card className="bg-primary/5 border-primary/20">
            <CardHeader>
              <CardTitle className="text-xl">Deadline reminders → Slack (1 & 7 days)</CardTitle>
              <CardDescription>
                Run hourly. LienDeadline returns reminders due now (deduped). Send to Slack.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Reminders URL Display */}
              <div>
                <label className="text-sm font-medium mb-2 block">Reminders URL</label>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono text-xs overflow-x-auto">
                    {`${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(`${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`, "reminders-url-top")}
                  >
                    {copied === "reminders-url-top" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Copy Buttons Row */}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(`${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`, "reminders-url-btn-top")}
                >
                  {copied === "reminders-url-btn-top" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Reminders URL
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(JSON.stringify(remindersHeadersTemplate, null, 2), "reminders-headers-top")}
                >
                  {copied === "reminders-headers-top" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Headers
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(remindersSlackMessageTemplate, "reminders-slack-message-top")}
                >
                  {copied === "reminders-slack-message-top" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Slack Message Template
                    </>
                  )}
                </Button>
              </div>

              {/* 3-Step Setup */}
              <div>
                <h4 className="text-sm font-semibold text-foreground mb-2">3-step setup</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
                  <li>
                    <span className="font-medium text-foreground">Trigger:</span> Schedule by Zapier → Every Hour
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Action:</span> Webhooks by Zapier → GET
                    <div className="mt-1 ml-4 text-xs">
                      URL: <code className="bg-muted px-1 rounded">/api/zapier/trigger/reminders?days=1,7&limit=50</code>
                    </div>
                    <div className="mt-1 ml-4 text-xs">
                      Header: <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;token&gt;</code>
                    </div>
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Action:</span> Slack → Send Channel Message (use template)
                  </li>
                </ol>
              </div>

              {/* Slack Message Template Display */}
              <div>
                <label className="text-sm font-medium mb-2 block">Slack Message Template</label>
                <div className="bg-muted/30 rounded-md p-3 text-xs">
                  <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                    {remindersSlackMessageTemplate}
                  </pre>
                  <p className="text-xs text-muted-foreground mt-2">
                    Use Zapier's field mapping to replace the <code className="bg-muted px-1 rounded">{`{{field}}`}</code> placeholders with actual values from the trigger response
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Golden Path Template - Invoice -> LienDeadline */}
          <Card className="bg-primary/5 border-primary/20">
            <CardHeader>
              <CardTitle className="text-xl">New Invoice → Create deadlines in LienDeadline</CardTitle>
              <CardDescription>
                The fastest way to get started. Send invoices from any system and automatically calculate lien deadlines.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Copy Buttons Row */}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(webhookUrl, "golden-webhook")}
                >
                  {copied === "golden-webhook" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Webhook URL
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(JSON.stringify(headersTemplate, null, 2), "golden-headers")}
                >
                  {copied === "golden-headers" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Headers
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(JSON.stringify(exampleJsonBody, null, 2), "golden-json")}
                >
                  {copied === "golden-json" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Example JSON Body
                    </>
                  )}
                </Button>
              </div>

              {/* Headers Display */}
              <div>
                <label className="text-sm font-medium mb-2 block">Headers</label>
                <div className="bg-muted/30 rounded-md p-3 text-xs">
                  <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(headersTemplate, null, 2)}
                  </pre>
                  <p className="text-xs text-muted-foreground mt-2 italic">
                    Replace YOUR_ZAPIER_TOKEN with your actual token from Dashboard → Integrations
                  </p>
                </div>
              </div>

              {/* Example JSON Body */}
              <div>
                <label className="text-sm font-medium mb-2 block">Example JSON Body</label>
                <div className="bg-muted/30 rounded-md p-3 text-xs">
                  <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(exampleJsonBody, null, 2)}
                  </pre>
                </div>
              </div>

              {/* Setup Instructions */}
              <div>
                <h4 className="text-sm font-semibold text-foreground mb-3">Zapier Setup Steps:</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
                  <li>
                    <span className="font-medium text-foreground">Trigger:</span> Choose your invoice source app (QuickBooks, Xero, Sage, Procore, Email Parser, Google Sheets, etc.) and select "New Invoice" event
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Action:</span> Add "Webhooks by Zapier" → Select "POST"
                  </li>
                  <li>
                    <span className="font-medium text-foreground">URL:</span> Paste the Webhook URL above
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Headers:</span> Paste the Headers JSON above (replace YOUR_ZAPIER_TOKEN with your token)
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Data:</span> Map fields from your trigger to the JSON body (state, invoice_date, invoice_amount_cents, project_name)
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Test:</span> Run a test and verify the project appears in Dashboard → Projects
                  </li>
                </ol>
              </div>
            </CardContent>
          </Card>

          {/* Deadline Reminders → Slack Card */}
          <Card className="bg-primary/5 border-primary/20">
            <CardHeader>
              <CardTitle className="text-xl">Deadline reminders → Slack (1 & 7 days)</CardTitle>
              <CardDescription>
                Run hourly. LienDeadline returns reminders due now (deduped). Send to Slack.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Reminders URL Display */}
              <div>
                <label className="text-sm font-medium mb-2 block">Reminders URL</label>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono text-xs overflow-x-auto">
                    {`${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(`${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`, "reminders-url")}
                  >
                    {copied === "reminders-url" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Copy Buttons Row */}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(`${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`, "reminders-url-btn")}
                >
                  {copied === "reminders-url-btn" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Reminders URL
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(JSON.stringify(remindersHeadersTemplate, null, 2), "reminders-headers")}
                >
                  {copied === "reminders-headers" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Headers
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(remindersSlackMessageTemplate, "reminders-slack-message")}
                >
                  {copied === "reminders-slack-message" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Slack Message Template
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(remindersZapSetupSteps, "reminders-zap-steps")}
                >
                  {copied === "reminders-zap-steps" ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copy Zap Setup Steps
                    </>
                  )}
                </Button>
              </div>

              {/* Zap Setup Steps Display */}
              <div>
                <h4 className="text-sm font-semibold text-foreground mb-2">Zap setup steps</h4>
                <div className="bg-muted/30 rounded-md p-3 text-xs">
                  <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                    {remindersZapSetupSteps}
                  </pre>
                </div>
              </div>

              {/* Slack Message Template Display */}
              <div>
                <label className="text-sm font-medium mb-2 block">Slack Message Template</label>
                <div className="bg-muted/30 rounded-md p-3 text-xs">
                  <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                    {remindersSlackMessageTemplate}
                  </pre>
                  <p className="text-xs text-muted-foreground mt-2">
                    Use Zapier's field mapping to replace the <code className="bg-muted px-1 rounded">{`{{field}}`}</code> placeholders with actual values from the trigger response
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* URL Reference Section */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">API Endpoints</CardTitle>
              <CardDescription>Copy these URLs to use in your Zapier workflows</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Webhook URL (POST)</label>
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
              <div>
                <label className="text-sm font-medium mb-2 block">Trigger URL (GET) - Upcoming deadlines</label>
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
              <div>
                <label className="text-sm font-medium mb-2 block">Reminders URL (GET) - Deduplicated reminders</label>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono text-xs overflow-x-auto">
                    {remindersUrl}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(remindersUrl, "reminders")}
                  >
                    {copied === "reminders" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Returns reminders for specified day offsets (default: 1,7 days) with server-side deduplication
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Zap Templates */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* REMINDERS_CARD_V1 */}
            {(() => {
              // Define constants directly in this card
              const remindersUrl = `${window.location.origin}/api/zapier/trigger/reminders?days=1,7&limit=50`;
              const remindersHeadersTemplate = `{"Authorization":"Bearer <YOUR_TOKEN_HERE>","Content-Type":"application/json"}`;
              const remindersSlackMessageTemplate = `🚨 Deadline Reminder: {{project.project_name}}
Invoice: {{project.invoice_number}}
Deadline: {{deadline_date}}
Type: {{reminder_type}} ({{reminder_days}} days remaining)
Amount: ${{`{{project.invoice_amount}}`}}`;
              const getRemindersZapSetupSteps = () => [
                "1) Trigger: Schedule by Zapier → Every Hour",
                "2) Action: Webhooks by Zapier → GET (use Reminders URL + Headers)",
                "3) Action: Slack → Send Channel Message (use Slack template)"
              ];
              const setupStepsText = getRemindersZapSetupSteps().join("\n");

              return (
                <Card key="reminders-card-v1" className="border border-orange-200 bg-orange-50">
                  <CardHeader>
                    <CardTitle>Deadline reminders → Slack (1 & 7 days) — REMINDERS_CARD_V1</CardTitle>
                    <CardDescription>
                      Run on a schedule. Sends alerts when deadlines are approaching.
                    </CardDescription>
                  </CardHeader>

                  <CardContent className="space-y-4 text-sm">
                    {/* Reminders URL */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">Reminders URL (GET)</label>
                      <div className="flex gap-2">
                        <code className="flex-1 px-3 py-2 bg-muted rounded-md text-xs font-mono overflow-x-auto">
                          {remindersUrl}
                        </code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => copyToClipboard(remindersUrl, "reminders-url-v1")}
                        >
                          {copied === "reminders-url-v1" ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>

                    {/* Headers */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">Headers</label>
                      <div className="flex gap-2">
                        <div className="flex-1 bg-muted/30 rounded-md p-3 text-xs">
                          <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                            {remindersHeadersTemplate}
                          </pre>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => copyToClipboard(remindersHeadersTemplate, "reminders-headers-v1")}
                        >
                          {copied === "reminders-headers-v1" ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>

                    {/* Slack Message Template */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">Slack Message Template</label>
                      <div className="flex gap-2">
                        <div className="flex-1 bg-muted/30 rounded-md p-3 text-xs">
                          <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                            {remindersSlackMessageTemplate}
                          </pre>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => copyToClipboard(remindersSlackMessageTemplate, "reminders-slack-v1")}
                        >
                          {copied === "reminders-slack-v1" ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>

                    {/* Setup Steps */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">Setup Steps</label>
                      <div className="flex gap-2">
                        <div className="flex-1 bg-muted/30 rounded-md p-3 text-xs">
                          <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                            {getRemindersZapSetupSteps().map((step, idx) => (
                              <li key={idx}>{step}</li>
                            ))}
                          </ol>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => copyToClipboard(setupStepsText, "reminders-steps-v1")}
                        >
                          {copied === "reminders-steps-v1" ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })()}

            {buildZapTemplates().map((zap) => (
              <Card key={zap.id} className="flex flex-col">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg mb-2">{zap.title}</CardTitle>
                      <CardDescription>{zap.description}</CardDescription>
                    </div>
                    <Badge variant="secondary">Template {zap.id}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 space-y-4">
                  {/* Trigger */}
                  <div>
                    <h4 className="text-sm font-semibold text-foreground mb-2">Trigger</h4>
                    <div className="bg-muted/50 rounded-md p-3 text-sm">
                      <div className="font-medium">{zap.trigger.app}</div>
                      <div className="text-muted-foreground text-xs mt-1">{zap.trigger.event}</div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div>
                    <h4 className="text-sm font-semibold text-foreground mb-2">Actions</h4>
                    <div className="space-y-2">
                      {zap.actions.map((action, idx) => (
                        <div key={idx} className="bg-muted/50 rounded-md p-3 text-sm">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-xs">
                              {action.type === "webhook" ? "POST" : action.type === "trigger" ? "GET" : action.type}
                            </Badge>
                            <span className="font-medium">{action.app}</span>
                          </div>
                          <div className="text-muted-foreground text-xs">{action.description}</div>
                          {action.url && (
                            <div className="mt-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-xs px-2"
                                onClick={() => copyToClipboard(action.url!, `zap-${zap.id}-${action.type}`)}
                              >
                                {copied === `zap-${zap.id}-${action.type}` ? (
                                  <>
                                    <Check className="h-3 w-3 mr-1" /> Copied
                                  </>
                                ) : (
                                  <>
                                    <Copy className="h-3 w-3 mr-1" /> Copy URL
                                  </>
                                )}
                              </Button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Webhook JSON Example */}
                  {zap.webhookExample && (
                    <div>
                      <h4 className="text-sm font-semibold text-foreground mb-2">Webhook JSON Example</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Required: state, invoice_date. Recommended: invoice_amount_cents, invoice_number. Optional: project_name, client_name.
                      </p>
                      <div className="bg-muted/30 rounded-md p-3 text-xs">
                        <pre className="text-muted-foreground font-mono whitespace-pre-wrap overflow-x-auto">
                          {JSON.stringify(zap.webhookExample, null, 2)}
                        </pre>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 text-xs px-2 mt-2"
                          onClick={() => copyToClipboard(JSON.stringify(zap.webhookExample, null, 2), `zap-${zap.id}-json`)}
                        >
                          {copied === `zap-${zap.id}-json` ? (
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
                  )}

                  {/* Field Mapping */}
                  <div>
                    <h4 className="text-sm font-semibold text-foreground mb-2">Field Mapping</h4>
                    <div className="bg-muted/30 rounded-md p-3 text-xs space-y-2">
                      {Object.entries(zap.fieldMapping).map(([key, fields]) => (
                        <div key={key}>
                          <div className="font-medium text-foreground mb-1 capitalize">{key}:</div>
                          <div className="pl-2 space-y-1">
                            {typeof fields === 'object' && Object.entries(fields).map(([field, desc]) => (
                              <div key={field} className="text-muted-foreground">
                                <code className="text-primary">{field}</code>: {desc as string}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Footer CTA */}
          <Card className="bg-primary/5 border-primary/20">
            <CardContent className="pt-6">
              <div className="text-center space-y-4">
                <h3 className="text-lg font-semibold text-foreground">Ready to build your Zap?</h3>
                <p className="text-sm text-muted-foreground">
                  Create your first Zap in Zapier using one of these templates.
                </p>
                <Button
                  onClick={() => window.open("https://zapier.com/apps/liendeadline/integrations", "_blank")}
                  className="bg-orange-600 hover:bg-orange-700 text-white"
                >
                  Open Zapier
                  <ExternalLink className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
    </>
  );
};

export default PopularZaps;

