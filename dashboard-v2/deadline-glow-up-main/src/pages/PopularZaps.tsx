import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Copy, Check, ExternalLink, ChevronDown, ChevronUp, Key, Rocket } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";

// Constants
const SOCIAL_PROOF_TEXT = "Used by contractors protecting $2.3M+ in receivables monthly";
const QUICK_START_SLACK_URL = "https://zapier.com/app/editor";

const PopularZaps = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [webhookUrl, setWebhookUrl] = useState("");
  const [triggerUrl, setTriggerUrl] = useState("");
  const [remindersUrl, setRemindersUrl] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [zapierToken, setZapierToken] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedCards, setExpandedCards] = useState<Record<number, boolean>>({});
  
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
  const remindersSlackMessageTemplate = "🔔 *LienDeadline reminder*\n\nProject: {{project__project_name}}\nDeadline: {{deadline_date}}\nReminder: {{reminder_type}} ({{reminder_days}} days before)\nState: {{project__state_code}}";
  
  // Zap setup steps for reminders (URL will be replaced dynamically)
  const getRemindersZapSetupSteps = (baseUrl: string) => `1) Trigger: Schedule by Zapier → Every Hour
2) Action: Webhooks by Zapier → GET
   URL: https://liendeadline.com/api/zapier/trigger/reminders?days=1,7&limit=10
   Header: Authorization: Bearer <token>
3) Action: Slack → Send Channel Message (use template)`;

  // --- Reminders Zap helpers (fix runtime crash) ---
  const getRemindersZapSetupStepsArray = () => [
    "1) Trigger: Schedule by Zapier → Every Hour",
    "2) Action: Webhooks by Zapier → GET",
    "3) URL: https://liendeadline.com/api/zapier/reminders/due",
    "4) Headers: Authorization: Bearer {{YOUR_ZAPIER_TOKEN}}",
    "5) Action: Slack → Send Channel Message",
    "6) Message: Use the template shown on this page (copy/paste)",
  ];

  const remindersZapSetupSteps = getRemindersZapSetupStepsArray();

  const renderRemindersZapSetupSteps = () => (
    <ol className="list-decimal pl-5 space-y-1">
      {remindersZapSetupSteps.map((s, i) => (
        <li key={i} className="text-sm text-muted-foreground">
          {s}
        </li>
      ))}
    </ol>
  );
  // --- end helpers ---

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
    setRemindersUrl(`https://liendeadline.com/api/zapier/trigger/reminders?days=1,7&limit=10`);
    
    // Fetch Zapier token status
    fetch('/api/zapier/token', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (data.has_token && data.last4) {
          // We can't show the full token, but we can show it exists
          setZapierToken(`••••${data.last4}`);
        }
      })
      .catch(() => {
        // Token fetch failed, user can generate one
      });
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
    const remindersUrlValue = remindersUrl || `https://liendeadline.com/api/zapier/trigger/reminders?days=1,7&limit=10`;
    
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
   URL: https://liendeadline.com/api/zapier/trigger/reminders?days=1,7&limit=10
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

  // Prevent runtime crash if API returns null/undefined items or missing app
  const safeZapTemplates = (zapTemplates ?? [])
    .filter(Boolean)
    .filter((z: any) => z && typeof z === "object")
    .map((z: any) => ({
      ...z,
      trigger: {
        ...z.trigger,
        app: z.trigger?.app ?? "Unknown app",
      },
      actions: (z.actions ?? []).map((action: any) => ({
        ...action,
        app: action?.app ?? "Unknown app",
      })),
    }));

  const toggleCardExpansion = (cardId: number) => {
    setExpandedCards(prev => ({
      ...prev,
      [cardId]: !prev[cardId]
    }));
  };

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />
      
      <main className="container py-8">
        <div className="space-y-8">
          {/* Back Button */}
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

          {/* A) Hero / Value Proposition */}
          <div className="space-y-4">
            <div>
              <h2 className="text-3xl font-bold text-foreground">Get deadline alerts wherever you already work</h2>
              <p className="text-muted-foreground mt-2 text-lg">
                Connect Zapier in minutes to send lien deadline reminders to Slack, email, CRM, or spreadsheets — powered by Zapier.
              </p>
            </div>

            <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
              <li>Works with 6,000+ apps</li>
              <li>No email setup inside LienDeadline</li>
              <li>LienDeadline decides when — Zapier decides where</li>
            </ul>

            <p className="text-sm text-muted-foreground italic">
              {SOCIAL_PROOF_TEXT}
            </p>
          </div>

          {/* B) Quick Start */}
          <Card id="quick-start" className="bg-primary/10 border-primary/30 shadow-lg scroll-mt-8">
            <CardHeader>
              <div className="flex items-center gap-2 mb-2">
                <Rocket className="h-6 w-6 text-primary" />
                <CardTitle className="text-2xl">🚀 Quick Start with Slack</CardTitle>
              </div>
              <CardDescription className="text-base">
                Get your first alert in under 5 minutes
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                size="lg"
                className="w-full md:w-auto"
                onClick={() => window.open(QUICK_START_SLACK_URL, '_blank')}
              >
                Connect QuickBooks → LienDeadline → Slack
                <ExternalLink className="h-4 w-4 ml-2" />
              </Button>
            </CardContent>
          </Card>

          {/* Popular Zap Templates Section */}
          <div className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground mb-1">Popular Zap Templates</h2>
              <p className="text-sm text-muted-foreground">Choose a template to get started. If no reminders are due, the Zap will not send anything.</p>
              <p className="text-sm text-foreground mt-2 font-medium">Most users start with Slack deadline reminders. You can add more automations later.</p>
            </div>

            {/* Simplified Zap Templates Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Reminders Template - Recommended */}
              <Card className="border-primary/30 shadow-md">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <CardTitle>Deadline reminders → Slack</CardTitle>
                        <Badge className="bg-primary text-primary-foreground">Recommended</Badge>
                      </div>
                      <CardDescription>
                        Sends Slack alerts when deadlines are approaching (1 & 7 days before).
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Trigger: Schedule by Zapier → Every Hour</p>
                    <p className="text-sm text-muted-foreground mb-2">Action: Webhooks GET → Slack Message</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(`https://liendeadline.com/api/zapier/trigger/reminders?days=1,7&limit=10`, "reminders-url-simple")}
                    >
                      {copied === "reminders-url-simple" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                      Copy URL
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(remindersSlackMessageTemplate, "reminders-slack-simple")}
                    >
                      {copied === "reminders-slack-simple" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                      Copy Template
                    </Button>
                  </div>
                  {expandedCards[0] && (
                    <div className="mt-3 pt-3 border-t space-y-4 text-xs">
                      {/* What Zapier will do */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">What Zapier will do</h4>
                        <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                          <li>Checks for reminders due today (1 or 7 days before deadlines)</li>
                          <li>Sends a Slack message for each reminder found</li>
                        </ul>
                      </div>

                      {/* Required Zapier steps */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">Required Zapier steps</h4>
                        <ol className="list-decimal list-inside space-y-1 text-muted-foreground ml-2">
                          <li>Trigger: Schedule by Zapier → Every Hour</li>
                          <li>Action: Webhooks by Zapier → GET</li>
                          <li className="ml-4">URL: <code className="bg-muted px-1 rounded">https://liendeadline.com/api/zapier/trigger/reminders?days=1,7&limit=10</code></li>
                          <li className="ml-4">Header: <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;your_token&gt;</code></li>
                          <li>Action: Slack → Send Channel Message</li>
                        </ol>
                      </div>

                      {/* Slack message template */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">Slack message template</h4>
                        <div className="bg-muted/30 p-2 rounded mt-1">
                          <pre className="whitespace-pre-wrap text-muted-foreground font-mono">{remindersSlackMessageTemplate}</pre>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 text-xs px-2 mt-2"
                            onClick={() => copyToClipboard(remindersSlackMessageTemplate, "reminders-slack-expanded")}
                          >
                            {copied === "reminders-slack-expanded" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                            Copy template
                          </Button>
                        </div>
                      </div>

                      {/* Advanced / Optional */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">Advanced / Optional</h4>
                        <div className="space-y-2">
                          <div>
                            <strong className="text-muted-foreground">Headers:</strong>
                            <pre className="bg-muted/30 p-2 rounded mt-1 text-muted-foreground font-mono">{JSON.stringify(remindersHeadersTemplate, null, 2)}</pre>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-xs px-2 mt-1"
                              onClick={() => copyToClipboard(JSON.stringify(remindersHeadersTemplate, null, 2), "reminders-headers-expanded")}
                            >
                              {copied === "reminders-headers-expanded" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                              Copy headers
                            </Button>
                          </div>
                          <p className="text-muted-foreground text-xs">
                            <strong>Note:</strong> If multiple reminders are returned, add Looping by Zapier to send one Slack message per reminder.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="w-full"
                    onClick={() => toggleCardExpansion(0)}
                  >
                    {expandedCards[0] ? "Hide Details" : "Show Details"}
                  </Button>
                </CardContent>
              </Card>

              {/* Invoice → LienDeadline Template */}
              <Card className="opacity-75 border-border/50">
                <CardHeader>
                  <CardTitle className="text-muted-foreground">New Invoice → Create deadlines</CardTitle>
                  <CardDescription className="text-muted-foreground/80">
                    Automatically calculate lien deadlines when invoices are created.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Trigger: Your Accounting System → New Invoice</p>
                    <p className="text-sm text-muted-foreground mb-2">Action: Webhooks POST → LienDeadline</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(webhookUrl, "webhook-simple")}
                    >
                      {copied === "webhook-simple" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                      Copy Webhook URL
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(JSON.stringify(headersTemplate, null, 2), "headers-simple")}
                    >
                      {copied === "headers-simple" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                      Copy Headers
                    </Button>
                  </div>
                  {expandedCards[1] && (
                    <div className="mt-3 pt-3 border-t space-y-4 text-xs">
                      {/* What Zapier will do */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">What Zapier will do</h4>
                        <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                          <li>Receives invoice data from your accounting system</li>
                          <li>Calculates lien deadlines and creates a project in LienDeadline</li>
                        </ul>
                      </div>

                      {/* Required Zapier steps */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">Required Zapier steps</h4>
                        <ol className="list-decimal list-inside space-y-1 text-muted-foreground ml-2">
                          <li>Trigger: Your Accounting System → New Invoice</li>
                          <li>Action: Webhooks by Zapier → POST</li>
                          <li className="ml-4">URL: <code className="bg-muted px-1 rounded">{webhookUrl}</code></li>
                          <li className="ml-4">Headers: <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;your_token&gt;</code></li>
                          <li>Data: Map invoice fields to JSON body (see Advanced section)</li>
                        </ol>
                      </div>

                      {/* Advanced / Optional */}
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">Advanced / Optional</h4>
                        <div className="space-y-2">
                          <div>
                            <strong className="text-muted-foreground">Example JSON body:</strong>
                            <pre className="bg-muted/30 p-2 rounded mt-1 text-muted-foreground font-mono">{JSON.stringify(exampleJsonBody, null, 2)}</pre>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-xs px-2 mt-1"
                              onClick={() => copyToClipboard(JSON.stringify(exampleJsonBody, null, 2), "invoice-json-expanded")}
                            >
                              {copied === "invoice-json-expanded" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                              Copy JSON
                            </Button>
                          </div>
                          <div>
                            <strong className="text-muted-foreground">Headers:</strong>
                            <pre className="bg-muted/30 p-2 rounded mt-1 text-muted-foreground font-mono">{JSON.stringify(headersTemplate, null, 2)}</pre>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-xs px-2 mt-1"
                              onClick={() => copyToClipboard(JSON.stringify(headersTemplate, null, 2), "invoice-headers-expanded")}
                            >
                              {copied === "invoice-headers-expanded" ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                              Copy headers
                            </Button>
                          </div>
                          <p className="text-muted-foreground text-xs">
                            <strong>Required fields:</strong> state, invoice_date<br />
                            <strong>Recommended:</strong> invoice_amount_cents, invoice_number<br />
                            <strong>Optional:</strong> project_name, client_name
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="w-full"
                    onClick={() => toggleCardExpansion(1)}
                  >
                    {expandedCards[1] ? "Hide Details" : "Show Details"}
                  </Button>
                </CardContent>
              </Card>

              {/* Other Templates */}
              {safeZapTemplates.filter(z => z.id > 1).map((zap) => (
                <Card key={zap.id} className="opacity-75 border-border/50">
                  <CardHeader>
                    <CardTitle className="text-base text-muted-foreground">{zap.title}</CardTitle>
                    <CardDescription className="text-xs text-muted-foreground/80">{zap.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div>
                      <p className="text-sm text-muted-foreground mb-1">
                        <strong>Trigger:</strong> {zap?.trigger?.app ?? "Unknown"}
                      </p>
                      <p className="text-sm text-muted-foreground mb-2">
                        <strong>Action:</strong> {zap.actions.map(a => a.app).join(" → ")}
                      </p>
                    </div>
                    {zap.actions.find(a => a.url) && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyToClipboard(zap.actions.find(a => a.url)!.url!, `zap-${zap.id}-url`)}
                      >
                        {copied === `zap-${zap.id}-url` ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                        Copy URL
                      </Button>
                    )}
                    {expandedCards[zap.id] && (
                      <div className="mt-3 pt-3 border-t space-y-4 text-xs">
                        {/* What Zapier will do */}
                        <div>
                          <h4 className="font-semibold text-foreground mb-2">What Zapier will do</h4>
                          <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                            <li>{zap.description}</li>
                          </ul>
                        </div>

                        {/* Required Zapier steps */}
                        <div>
                          <h4 className="font-semibold text-foreground mb-2">Required Zapier steps</h4>
                          <ol className="list-decimal list-inside space-y-1 text-muted-foreground ml-2">
                            <li>Trigger: {zap?.trigger?.app ?? "Unknown"} → {zap?.trigger?.event ?? ""}</li>
                            {zap.actions.map((action, idx) => (
                              <li key={idx}>
                                Action: {action.app} → {action.description}
                                {action.url && (
                                  <span className="ml-2">
                                    (<code className="bg-muted px-1 rounded text-xs">{action.type === "webhook" ? "POST" : "GET"}</code>)
                                  </span>
                                )}
                              </li>
                            ))}
                          </ol>
                        </div>

                        {/* Advanced / Optional */}
                        {(zap.webhookExample || zap.fieldMapping) && (
                          <div>
                            <h4 className="font-semibold text-foreground mb-2">Advanced / Optional</h4>
                            <div className="space-y-2">
                              {zap.webhookExample && (
                                <div>
                                  <strong className="text-muted-foreground">Example JSON:</strong>
                                  <pre className="bg-muted/30 p-2 rounded mt-1 text-muted-foreground font-mono">{JSON.stringify(zap.webhookExample, null, 2)}</pre>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-6 text-xs px-2 mt-1"
                                    onClick={() => copyToClipboard(JSON.stringify(zap.webhookExample, null, 2), `zap-${zap.id}-json-expanded`)}
                                  >
                                    {copied === `zap-${zap.id}-json-expanded` ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                                    Copy JSON
                                  </Button>
                                </div>
                              )}
                              {zap.fieldMapping && (
                                <div>
                                  <strong className="text-muted-foreground">Field mapping:</strong>
                                  <div className="bg-muted/30 p-2 rounded mt-1 space-y-2">
                                    {Object.entries(zap.fieldMapping ?? {}).map(([key, fields]) => (
                                      <div key={key}>
                                        <div className="font-medium text-muted-foreground mb-1 capitalize">{key}:</div>
                                        <div className="pl-2 space-y-1">
                                          {typeof fields === 'object' && Object.entries(fields ?? {}).map(([field, desc]) => (
                                            <div key={field} className="text-muted-foreground text-xs">
                                              <code className="text-primary">{field}</code>: {desc as string}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {(zap.webhookExample || zap.fieldMapping || zap.actions.find(a => a.url)) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="w-full"
                        onClick={() => toggleCardExpansion(zap.id)}
                      >
                        {expandedCards[zap.id] ? "Hide Details" : "Show Details"}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* D) Advanced Setup (Optional) - Collapsed by default */}
          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <div className="space-y-3">
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between p-0 h-auto">
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-semibold text-foreground">Advanced Setup (Optional)</h2>
                  </div>
                  {showAdvanced ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <Card>
                  <CardContent className="pt-6 space-y-4">
                    <p className="text-sm text-muted-foreground mb-4">
                      Use these only if you want to build a custom Zap from scratch.
                    </p>

                    {/* Zapier API Token */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Key className="h-4 w-4 text-muted-foreground" />
                        <label className="text-sm font-medium">Zapier API Token</label>
                      </div>
                      <div className="flex items-center gap-3">
                        <Input
                          type="text"
                          value={zapierToken || "Generate token from Dashboard → Integrations"}
                          readOnly
                          className="flex-1 font-mono text-sm"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate('/')}
                        >
                          Get Token
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Generate your Zapier API token from the Integrations page. Use it in all Zapier webhook headers.
                      </p>
                    </div>

                    <div className="border-t pt-4 space-y-4">
                      <div>
                        <label className="text-sm font-medium mb-2 block">Webhook URL (POST)</label>
                        <div className="flex gap-2">
                          <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono text-xs overflow-x-auto">
                            {webhookUrl}
                          </code>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => copyToClipboard(webhookUrl, "webhook-advanced")}
                          >
                            {copied === "webhook-advanced" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
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
                            onClick={() => copyToClipboard(triggerUrl, "trigger-advanced")}
                          >
                            {copied === "trigger-advanced" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
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
                            onClick={() => copyToClipboard(remindersUrl, "reminders-advanced")}
                          >
                            {copied === "reminders-advanced" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                          </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Returns reminders for specified day offsets (default: 1,7 days) with server-side deduplication
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </CollapsibleContent>
            </div>
          </Collapsible>
        </div>
      </main>
    </div>
  );
};

export default PopularZaps;

