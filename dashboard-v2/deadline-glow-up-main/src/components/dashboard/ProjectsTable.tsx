import { useState, useEffect } from "react";
import { RefreshCw, FileSpreadsheet, FileText, Eye, Calendar, Download } from "lucide-react";
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
  reminder_1day: number;
  reminder_7days: number;
}

export const ProjectsTable = () => {
  const { toast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

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
                    {(project.reminder_1day || project.reminder_7days) ? (
                      <Badge className="bg-info/15 text-info border-info/30">
                        <Calendar className="h-3 w-3 mr-1" />
                        {[
                          project.reminder_1day ? "1 Day" : null, 
                          project.reminder_7days ? "7 Days" : null
                        ].filter(Boolean).join(", ")}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-sm">None</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-2">
                      <Button 
                        size="sm" 
                        className="bg-primary hover:bg-primary/90 text-primary-foreground"
                        onClick={() => handleDownloadPDF(project.id)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
