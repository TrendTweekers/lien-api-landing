import { useState, useEffect } from "react";
import { RefreshCw, FileSpreadsheet, FileText, Eye, Calendar, Download, Trash2, Bell, ChevronDown, ChevronUp } from "lucide-react";
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
import { NotificationSettings } from "./NotificationSettings";

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

export const ProjectsTable = () => {
  const { toast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedProjectId, setExpandedProjectId] = useState<number | null>(null);

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
                 <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">Loading projects...</TableCell>
               </TableRow>
            ) : projects.length === 0 ? (
               <TableRow>
                 <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">No projects found.</TableCell>
               </TableRow>
            ) : (
              projects.map((project) => (
                <>
                  <TableRow key={project.id} className="border-border hover:bg-muted/30">
                    <TableCell>
                      <div>
                        <p className="font-medium text-foreground">{project.project_name || "Unnamed Project"}</p>
                        <p className="text-xs text-muted-foreground">{project.description}</p>
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
                        // CRITICAL: Handle boolean, number (0/1), null, undefined
                        // Default to reminder_1day = true (1 Day enabled) if null/undefined
                        // Default to reminder_7days = false (7 Days disabled) if null/undefined
                        let r1day: boolean;
                        let r7days: boolean;
                        
                        if (project.reminder_1day === null || project.reminder_1day === undefined) {
                          r1day = true;  // Default to enabled (1 Day)
                        } else if (typeof project.reminder_1day === 'boolean') {
                          r1day = project.reminder_1day;
                        } else if (typeof project.reminder_1day === 'number') {
                          r1day = project.reminder_1day !== 0;  // 1 = true, 0 = false
                        } else {
                          r1day = Boolean(project.reminder_1day);
                        }
                        
                        if (project.reminder_7days === null || project.reminder_7days === undefined) {
                          r7days = false;  // Default to disabled (7 Days)
                        } else if (typeof project.reminder_7days === 'boolean') {
                          r7days = project.reminder_7days;
                        } else if (typeof project.reminder_7days === 'number') {
                          r7days = project.reminder_7days !== 0;  // 1 = true, 0 = false
                        } else {
                          r7days = Boolean(project.reminder_7days);
                        }
                        
                        // Display badges if at least one reminder is enabled
                        if (r1day || r7days) {
                          const badges = [];
                          if (r1day) badges.push("1 Day");
                          if (r7days) badges.push("7 Days");
                          return (
                            <Badge className="bg-info/15 text-info border-info/30">
                              <Calendar className="h-3 w-3 mr-1" />
                              {badges.join(", ")}
                            </Badge>
                          );
                        }
                        return <span className="text-muted-foreground text-sm">None</span>;
                      })()}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-2">
                        <div className="text-xs text-muted-foreground mr-2">
                          Expanded: {expandedProjectId === project.id ? "YES" : "NO"}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs text-muted-foreground hover:text-foreground"
                          onClick={() => {
                            console.log("[NOTIF CLICK]", project.id);
                            setExpandedProjectId(expandedProjectId === project.id ? null : project.id);
                          }}
                        >
                          <Bell className="h-3 w-3 mr-1" />
                          Notifications
                          {expandedProjectId === project.id ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
                        </Button>
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
                    <TableRow>
                      <TableCell colSpan={9} className="p-4">
                        <div style={{
                          border: "4px solid red",
                          background: "yellow",
                          padding: "16px",
                          fontSize: "18px",
                          fontWeight: "bold"
                        }}>
                          EXPANDED ROW RENDERED ✅ projectId={project.id} name={project.project_name}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
