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
        description: "URL copied to clipboard",
      });
      setTimeout(() => setCopied(null), 1500);
    });
  };

  const zapTemplates = [
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

  return (
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
            <h1 className="text-3xl font-bold text-foreground mb-2">Popular Zaps</h1>
            <p className="text-muted-foreground">Pick a template. Build it in Zapier in minutes.</p>
          </div>

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
                <label className="text-sm font-medium mb-2 block">Trigger URL (GET)</label>
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
            </CardContent>
          </Card>

          {/* Zap Templates */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {zapTemplates.map((zap) => (
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
  );
};

export default PopularZaps;

