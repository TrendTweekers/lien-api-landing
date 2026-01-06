import { useState, useEffect } from "react";
import { RefreshCw, FileSpreadsheet, FileText, Eye, Calendar, Download, Trash2, Bell, ChevronDown, ChevronUp, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { usePlan } from "@/hooks/usePlan";
import { NotificationSettings } from "./NotificationSettings";
import { UpgradeModal } from "@/components/UpgradeModal";

interface Project {
  id: number;
  project_name: string;
  description?: string;
  client_name: string;
  invoice_date?: string;
  amount: number;
  state: string;
  prelim_deadline: string;
  lien_deadline: string;
  reminder_1day: boolean | number | null | undefined;  // Can be boolean, number (0/1), or null
  reminder_7days: boolean | number | null | undefined;  // Can be boolean, number (0/1), or null
}

interface ProjectsTableProps {
  expandedProjectId?: number | null;
  onExpandedProjectChange?: (projectId: number | null) => void;
}

export const ProjectsTable = ({ expandedProjectId: externalExpandedProjectId, onExpandedProjectChange }: ProjectsTableProps = {}) => {
  const { toast } = useToast();
  const { planInfo } = usePlan();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [internalExpandedProjectId, setInternalExpandedProjectId] = useState<number | null>(null);
  const [flashProjectId, setFlashProjectId] = useState<string | null>(null);
  const [projectNotificationStatuses, setProjectNotificationStatuses] = useState<Record<number, { zapierEnabled: boolean; reminderOffsetsDays: number[] }>>({});
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  
  // Reminders eligibility: Basic+ plans can use reminders
  const remindersEligible = planInfo.plan === "basic" || planInfo.plan === "automated" || planInfo.plan === "enterprise";
  
  // Use external expandedProjectId if provided, otherwise use internal state
  const expandedProjectId = externalExpandedProjectId !== undefined ? externalExpandedProjectId : internalExpandedProjectId;
  const setExpandedProjectId = (id: number | null) => {
    if (onExpandedProjectChange) {
      onExpandedProjectChange(id);
    } else {
      setInternalExpandedProjectId(id);
    }
  };

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/calculations/history", { headers });
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();
      // Ensure history is an array
      const historyArray = Array.isArray(data.history) ? data.history : (Array.isArray(data) ? data : []);
      setProjects(historyArray);
    } catch (e) {
      console.error(e);
      toast({
        title: "Error",
        description: "Failed to load projects.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  // Fetch notification status for all projects
  const fetchProjectNotificationStatuses = async () => {
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // Fetch notification settings for all projects in parallel
      const notificationPromises = projects.map(async (project) => {
        try {
          const res = await fetch(`/api/projects/${project.id}/notifications`, { headers });
          if (!res.ok) {
            return {
              projectId: project.id,
              zapierEnabled: false,
              reminderOffsetsDays: []
            };
          }
          const data = await res.json();
          return {
            projectId: project.id,
            zapierEnabled: data.zapier_enabled === true,
            reminderOffsetsDays: data.reminder_offsets_days || []
          };
        } catch (error) {
          return {
            projectId: project.id,
            zapierEnabled: false,
            reminderOffsetsDays: []
          };
        }
      });

      const statuses = await Promise.all(notificationPromises);
      const statusMap: Record<number, { zapierEnabled: boolean; reminderOffsetsDays: number[] }> = {};
      statuses.forEach((status) => {
        statusMap[status.projectId] = {
          zapierEnabled: status.zapierEnabled,
          reminderOffsetsDays: status.reminderOffsetsDays
        };
      });
      setProjectNotificationStatuses(statusMap);
    } catch (error) {
      console.error('Error fetching project notification statuses:', error);
    }
  };

  useEffect(() => {
    fetchProjects();

    const handleProjectSaved = () => {
      fetchProjects();
    };

    window.addEventListener('project-saved', handleProjectSaved);

    return () => {
      window.removeEventListener('project-saved', handleProjectSaved);
    };
  }, []);

  // Fetch notification statuses when projects change
  useEffect(() => {
    if (projects.length > 0) {
      fetchProjectNotificationStatuses();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects.length]);

  const handleDownloadPDF = async (id: number) => {
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/calculations/${id}/pdf`, { headers });
      if (!res.ok) throw new Error("Download failed");
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `deadline-report-${id}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast({
        title: "Success",
        description: "PDF downloaded successfully.",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to download PDF.",
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async (id: number) => {
    if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      return;
    }

    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/calculations/${id}`, {
        method: 'DELETE',
        headers
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Failed to delete project" }));
        throw new Error(errorData.detail || "Failed to delete project");
      }

      const data = await res.json();
      
      // Remove from local state immediately for instant UI update
      setProjects(projects.filter(p => p.id !== id));
      
      toast({
        title: "Success",
        description: "Project deleted successfully.",
      });

      // If this was a QuickBooks invoice, trigger a refresh of the invoices table
      if (data.quickbooks_invoice_id) {
        // Dispatch event to refresh imported invoices
        window.dispatchEvent(new CustomEvent('project-deleted', { 
          detail: { quickbooks_invoice_id: data.quickbooks_invoice_id } 
        }));
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to delete project.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="bg-card rounded-xl overflow-hidden border border-border card-shadow">
      <div className="p-6 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-foreground">Your Projects</h2>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="border-border hover:bg-muted"
            onClick={fetchProjects}
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button size="sm" className="bg-success hover:bg-success/90 text-success-foreground">
            <FileSpreadsheet className="h-4 w-4 mr-1.5" />
            Export to CSV
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent bg-muted/50">
              <TableHead className="text-foreground font-semibold">Project</TableHead>
              <TableHead className="text-foreground font-semibold">Client</TableHead>
              <TableHead className="text-foreground font-semibold">Invoice Date</TableHead>
              <TableHead className="text-foreground font-semibold">Amount</TableHead>
              <TableHead className="text-foreground font-semibold">State</TableHead>
              <TableHead className="text-foreground font-semibold">Prelim Deadline</TableHead>
              <TableHead className="text-foreground font-semibold">Lien Deadline</TableHead>
              <TableHead className="text-foreground font-semibold">Reminders</TableHead>
              <TableHead className="text-foreground font-semibold text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
               <TableRow>
                 <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">Loading projects...</TableCell>
               </TableRow>
            ) : projects.length === 0 ? (
               <TableRow>
                 <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">No projects found.</TableCell>
               </TableRow>
            ) : (
              projects.map((project) => {
                const notificationStatus = projectNotificationStatuses[project.id];
                const alertsEnabled = notificationStatus?.zapierEnabled && notificationStatus?.reminderOffsetsDays.length > 0;
                
                return (
                <>
                  <TableRow 
                    key={project.id} 
                    className={`border-border hover:bg-muted/30 ${alertsEnabled ? 'bg-success/5' : ''}`}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {alertsEnabled && (
                          <Bell className="h-4 w-4 text-success flex-shrink-0" />
                        )}
                        <div>
                          <p className="font-medium text-foreground">{project.project_name || "Unnamed Project"}</p>
                          <p className="text-xs text-muted-foreground">{project.description}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-foreground">{project.client_name}</TableCell>
                    <TableCell className="text-foreground">
                      {project.invoice_date ? new Date(project.invoice_date).toLocaleDateString("en-US", { year: 'numeric', month: 'short', day: 'numeric' }) : "-"}
                    </TableCell>
                    <TableCell className="font-semibold text-foreground">
                      ${typeof project.amount === 'number' ? project.amount.toLocaleString() : project.amount}
                    </TableCell>
                    <TableCell>
                      <Badge className="bg-warning/15 text-warning border-warning/30 hover:bg-warning/20">
                        {project.state}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-foreground">{project.prelim_deadline}</TableCell>
                    <TableCell className="text-foreground">{project.lien_deadline}</TableCell>
                    <TableCell>
                      {(() => {
                        // Plan gate: Free plan users see locked state
                        if (!remindersEligible) {
                          return (
                            <span
                              onClick={() => setUpgradeModalOpen(true)}
                              className="text-muted-foreground text-sm cursor-pointer hover:text-foreground flex items-center gap-1"
                            >
                              <Lock className="h-3 w-3" />
                              Upgrade to enable reminders
                            </span>
                          );
                        }
                        
                        // Check notification settings first (new system)
                        const notificationStatus = projectNotificationStatuses[project.id];
                        if (notificationStatus) {
                          const alertsEnabled = notificationStatus.zapierEnabled && notificationStatus.reminderOffsetsDays.length > 0;
                          if (alertsEnabled) {
                            const offsets = notificationStatus.reminderOffsetsDays.map(d => `${d}d`).join(", ");
                            return (
                              <Badge className="bg-success/15 text-success border-success/30">
                                <Bell className="h-3 w-3 mr-1" />
                                Alerts on ({offsets})
                              </Badge>
                            );
                          } else {
                            return (
                              <button
                                type="button"
                                onClick={() => {
                                  const isExpanding = expandedProjectId !== project.id;
                                  const newExpandedId = isExpanding ? project.id : null;
                                  setExpandedProjectId(newExpandedId);
                                  
                                  if (isExpanding) {
                                    setFlashProjectId(String(project.id));
                                    requestAnimationFrame(() => {
                                      const anchorId = `notif-panel-${project.id}`;
                                      const anchorElement = document.getElementById(anchorId);
                                      if (anchorElement) {
                                        anchorElement.scrollIntoView({ 
                                          behavior: "smooth", 
                                          block: "nearest" 
                                        });
                                      }
                                    });
                                    setTimeout(() => {
                                      setFlashProjectId(null);
                                    }, 1500);
                                  }
                                }}
                                className="text-primary hover:text-primary/80 text-sm font-medium underline underline-offset-2"
                              >
                                Set up alerts
                              </button>
                            );
                          }
                        }
                        
                        // Fallback to legacy reminder fields if notification status not loaded yet
                        let r1day: boolean;
                        let r7days: boolean;
                        
                        if (project.reminder_1day === null || project.reminder_1day === undefined) {
                          r1day = false;
                        } else if (typeof project.reminder_1day === 'boolean') {
                          r1day = project.reminder_1day;
                        } else if (typeof project.reminder_1day === 'number') {
                          r1day = project.reminder_1day !== 0;
                        } else {
                          r1day = Boolean(project.reminder_1day);
                        }
                        
                        if (project.reminder_7days === null || project.reminder_7days === undefined) {
                          r7days = false;
                        } else if (typeof project.reminder_7days === 'boolean') {
                          r7days = project.reminder_7days;
                        } else if (typeof project.reminder_7days === 'number') {
                          r7days = project.reminder_7days !== 0;
                        } else {
                          r7days = Boolean(project.reminder_7days);
                        }
                        
                        if (r1day || r7days) {
                          const badges = [];
                          if (r1day) badges.push("1d");
                          if (r7days) badges.push("7d");
                          return (
                            <Badge className="bg-success/15 text-success border-success/30">
                              <Bell className="h-3 w-3 mr-1" />
                              Alerts on ({badges.join(", ")})
                            </Badge>
                          );
                        }
                        
                        return (
                          <button
                            type="button"
                            onClick={() => {
                              const isExpanding = expandedProjectId !== project.id;
                              const newExpandedId = isExpanding ? project.id : null;
                              setExpandedProjectId(newExpandedId);
                              
                              if (isExpanding) {
                                setFlashProjectId(String(project.id));
                                requestAnimationFrame(() => {
                                  const anchorId = `notif-panel-${project.id}`;
                                  const anchorElement = document.getElementById(anchorId);
                                  if (anchorElement) {
                                    anchorElement.scrollIntoView({ 
                                      behavior: "smooth", 
                                      block: "nearest" 
                                    });
                                  }
                                });
                                setTimeout(() => {
                                  setFlashProjectId(null);
                                }, 1500);
                              }
                            }}
                            className="text-primary hover:text-primary/80 text-sm font-medium underline underline-offset-2"
                          >
                            Set up alerts
                          </button>
                        );
                      })()}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            const isExpanding = expandedProjectId !== project.id;
                            const newExpandedId = isExpanding ? project.id : null;
                            setExpandedProjectId(newExpandedId);
                            
                            // Auto-scroll and highlight only when expanding
                            if (isExpanding) {
                              setFlashProjectId(String(project.id));
                              
                              // Wait for DOM paint, then scroll into view
                              requestAnimationFrame(() => {
                                const anchorId = `notif-panel-${project.id}`;
                                const anchorElement = document.getElementById(anchorId);
                                if (anchorElement) {
                                  anchorElement.scrollIntoView({ 
                                    behavior: "smooth", 
                                    block: "nearest" 
                                  });
                                }
                              });
                              
                              // Clear highlight after 1.5s
                              setTimeout(() => {
                                setFlashProjectId(null);
                              }, 1500);
                            }
                          }}
                          className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground font-medium"
                        >
                          <Bell className="h-3 w-3" />
                          <span>{expandedProjectId === project.id ? "Hide notifications" : "Notifications"}</span>
                          <ChevronDown
                            className={[
                              "h-4 w-4 transition-transform duration-200",
                              expandedProjectId === project.id ? "rotate-180" : "rotate-0",
                            ].join(" ")}
                          />
                        </button>
                        <Button 
                          size="sm" 
                          className="bg-primary hover:bg-primary/90 text-primary-foreground"
                          onClick={() => handleDownloadPDF(project.id)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="border-destructive/30 hover:bg-destructive/10 hover:border-destructive/50 text-destructive"
                          onClick={() => handleDeleteProject(project.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  {expandedProjectId === project.id && (
                    <TableRow id={`notif-panel-${project.id}`} className={flashProjectId === String(project.id) ? "bg-orange-50/40 ring-1 ring-orange-200" : ""}>
                      <TableCell colSpan={9} className="pt-4 pb-4 px-4">
                        <NotificationSettings projectId={String(project.id)} projectName={project.project_name} />
                      </TableCell>
                    </TableRow>
                  )}
                </>
              );
              })
            )}
          </TableBody>
        </Table>
      </div>
      
      <UpgradeModal open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen} />
    </div>
  );
};
