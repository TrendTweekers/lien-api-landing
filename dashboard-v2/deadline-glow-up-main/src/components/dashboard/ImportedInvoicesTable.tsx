import { useState, useEffect } from "react";
import { RefreshCw, Save, Info } from "lucide-react";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

import { calculateStateDeadline } from "@/utils/deadlineCalculator";

interface Invoice {
  id: string;
  invoice_number: string;
  customer_name: string;
  date: string;
  amount: number;
  balance: number;
  status: string;
  state: string;
  preliminary_deadline: string | null;
  lien_deadline: string | null;
  prelim_days_remaining: number | null;
  lien_days_remaining: number | null;
  project_type: "Commercial" | "Residential";
  project_state: string;
}

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
];

export const ImportedInvoicesTable = ({ onProjectSaved }: { onProjectSaved?: () => void }) => {
  const { toast } = useToast();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);

  const calculateDeadlines = (invoiceDateStr: string, type: "Commercial" | "Residential", state: string) => {
    const invoiceDate = new Date(invoiceDateStr);
    
    // Use the shared utility for Single Source of Truth
    const { preliminaryNotice, lienFiling } = calculateStateDeadline(
      state, 
      invoiceDate, 
      type.toLowerCase() as "commercial" | "residential",
      "supplier" // Defaulting to supplier role for imported invoices
    );

    const today = new Date();
    // Normalize to start of day for accurate calculation
    today.setHours(0, 0, 0, 0);
    
    const pDate = new Date(preliminaryNotice);
    pDate.setHours(0, 0, 0, 0);
    
    const lDate = new Date(lienFiling);
    lDate.setHours(0, 0, 0, 0);

    const prelimDays = Math.ceil((pDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    const lienDays = Math.ceil((lDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

    return {
      preliminary_deadline: preliminaryNotice.toISOString(),
      lien_deadline: lienFiling.toISOString(),
      prelim_days_remaining: prelimDays,
      lien_days_remaining: lienDays
    };
  };

  const handleProjectTypeChange = (id: string, newType: "Commercial" | "Residential") => {
    setInvoices(prevInvoices => prevInvoices.map(inv => {
      if (inv.id === id) {
        const newDeadlines = calculateDeadlines(inv.date, newType, inv.project_state);
        return {
          ...inv,
          project_type: newType,
          ...newDeadlines
        };
      }
      return inv;
    }));
  };

  const handleStateChange = (id: string, newState: string) => {
    setInvoices(prevInvoices => prevInvoices.map(inv => {
      if (inv.id === id) {
        const newDeadlines = calculateDeadlines(inv.date, inv.project_type, newState);
        return {
          ...inv,
          project_state: newState,
          ...newDeadlines
        };
      }
      return inv;
    }));
  };

  const handleSaveToProjects = async (invoice: Invoice) => {
    console.log("Saving to projects:", invoice);
    
    // Calculate deadlines to ensure we save accurate data
    const rawDeadlines = calculateStateDeadline(
      invoice.project_state,
      new Date(invoice.date),
      invoice.project_type.toLowerCase() as "commercial" | "residential",
      "supplier"
    );

    const preliminaryNotice = adjustForBusinessDays(rawDeadlines.preliminaryNotice);
    const lienFiling = adjustForBusinessDays(rawDeadlines.lienFiling);

    const payload = {
      project_name: invoice.customer_name,
      client_name: invoice.customer_name,
      state: invoice.project_state,
      state_code: invoice.project_state,
      invoice_date: invoice.date,
      invoice_amount: invoice.amount,
      project_type: invoice.project_type,
      status: "Active",
      prelim_deadline: preliminaryNotice.deadline ? preliminaryNotice.deadline.toISOString().split('T')[0] : null,
      lien_deadline: lienFiling.deadline ? lienFiling.deadline.toISOString().split('T')[0] : null,
      reminder_1day: false,
      reminder_7days: false,
    };

    try {
      const token = localStorage.getItem('session_token');
      const res = await fetch("/api/calculations/save", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to save project");
      }

      toast({
        title: "Project saved successfully!",
        description: `Invoice #${invoice.invoice_number} saved as ${invoice.customer_name}.`,
        className: "bg-green-50 border-green-200 text-green-800",
      });

      // Remove the saved invoice from the list to prevent double-saving
      setInvoices(prev => prev.filter(i => i.id !== invoice.id));

      // Trigger refresh of the Projects table
      if (onProjectSaved) {
        onProjectSaved();
      }

    } catch (error) {
      console.error("Save error:", error);
      toast({
        title: "Error saving project",
        description: error instanceof Error ? error.message : "An unknown error occurred",
        variant: "destructive",
      });
    }
  };

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/quickbooks/invoices", { headers });
      
      if (res.status === 404) {
        setConnected(false);
        setLoading(false);
        return;
      }

      if (!res.ok) throw new Error("Failed to fetch invoices");
      
      const data = await res.json();
      // Ensure data is an array before setting it
      const invoicesList = Array.isArray(data) ? data : [];
      
      // Add default project_type and ensure calculations match default
      const processedList = invoicesList.map((inv: any) => {
        const projectState = inv.project_state || "TX"; // Default to Texas if not present
        const projectType = inv.project_type || "Commercial";
        
        // Ensure deadlines are calculated with the latest robust logic immediately on load
        const calculated = calculateDeadlines(inv.date, projectType, projectState);
        
        return {
          ...inv,
          project_type: projectType,
          project_state: projectState,
          ...calculated
        };
      });

      setInvoices(processedList);
      setConnected(true);
    } catch (e) {
      console.error(e);
      // Only show error toast if we thought we were connected
      if (connected) {
        toast({
            title: "Error",
            description: "Failed to load invoices.",
            variant: "destructive",
        });
      }
      // Ensure invoices is an array on error
      setInvoices([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, []);

  if (!connected && !loading) return null;

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleDateString("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric",
      });
    } catch (e) {
      return "Invalid Date";
    }
  };

  const getDaysBadge = (days: number | null) => {
    if (days === null) return null;
    
    if (days < 0) {
       return (
        <Badge variant="destructive" className="bg-destructive/15 text-destructive border-destructive/30 hover:bg-destructive/25 whitespace-nowrap">
           Overdue
        </Badge>
       );
    }
    
    if (days < 10) {
      return (
        <Badge className="bg-destructive/15 text-destructive border-destructive/30 hover:bg-destructive/25 whitespace-nowrap">
          {days} days
        </Badge>
      );
    }
    
    if (days > 30) {
      return (
        <Badge className="bg-success/15 text-success border-success/30 hover:bg-success/25 whitespace-nowrap">
          {days} days
        </Badge>
      );
    }
    
    return (
      <Badge className="bg-warning/15 text-warning border-warning/30 hover:bg-warning/25 whitespace-nowrap">
        {days} days
      </Badge>
    );
  };

  return (
    <div className="bg-card rounded-xl overflow-hidden border border-border card-shadow mt-8 animate-slide-up" style={{ animationDelay: "0.22s" }}>
      <div className="p-6 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <div className="bg-blue-500/10 p-1.5 rounded-md">
                    <span className="text-blue-500 font-bold text-xs">QB</span>
                </div>
                Imported Invoices
            </h2>
            <p className="text-sm text-muted-foreground">Recent invoices from QuickBooks with calculated deadlines</p>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          className="border-border hover:bg-muted"
          onClick={fetchInvoices}
        >
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Sync Now
        </Button>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent bg-muted/50">
              <TableHead className="text-foreground font-semibold">Invoice #</TableHead>
              <TableHead className="text-foreground font-semibold">Customer</TableHead>
              <TableHead className="text-foreground font-semibold">
                <div className="flex items-center gap-1">
                  Date
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info 
                          className="h-4 w-4 text-muted-foreground hover:text-foreground cursor-help" 
                          style={{ display: 'inline-block', opacity: 1 }}
                        />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-[300px] z-50 bg-popover text-popover-foreground shadow-md border border-border">
                        <p>Deadlines are calculated based on the Invoice Creation Date (Work Date), not the Payment Due Date. Most state lien laws begin counting from the date services were performed.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </TableHead>
              <TableHead className="text-foreground font-semibold">Amount</TableHead>
              <TableHead className="text-foreground font-semibold">State</TableHead>
              <TableHead className="text-foreground font-semibold">Type</TableHead>
              <TableHead className="text-foreground font-semibold">Prelim Deadline</TableHead>
              <TableHead className="text-foreground font-semibold">Lien Deadline</TableHead>
              <TableHead className="text-foreground font-semibold">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
               <TableRow>
                 <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">Loading invoices...</TableCell>
               </TableRow>
            ) : (!invoices || invoices.length === 0) ? (
               <TableRow>
                 <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">No invoices found in the last 90 days.</TableCell>
               </TableRow>
            ) : (
              invoices.map((inv) => (
                <TableRow key={inv.id} className="border-border hover:bg-muted/30">
                  <TableCell className="font-medium text-foreground">{inv.invoice_number}</TableCell>
                  <TableCell className="text-foreground">{inv.customer_name}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(inv.date)}</TableCell>
                  <TableCell className="font-semibold text-foreground">
                    ${inv.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </TableCell>
                  <TableCell>
                    <Select 
                      value={inv.project_state} 
                      onValueChange={(val) => handleStateChange(inv.id, val)}
                    >
                      <SelectTrigger className="h-8 w-[70px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="max-h-[200px]">
                        {US_STATES.map((state) => (
                          <SelectItem key={state} value={state}>
                            {state}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Select 
                      value={inv.project_type} 
                      onValueChange={(val: "Commercial" | "Residential") => handleProjectTypeChange(inv.id, val)}
                    >
                      <SelectTrigger className="h-8 w-[130px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Commercial">Commercial</SelectItem>
                        <SelectItem value="Residential">Residential</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                        <span className="text-foreground">{formatDate(inv.preliminary_deadline)}</span>
                        {getDaysBadge(inv.prelim_days_remaining)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                        <span className="text-foreground">{formatDate(inv.lien_deadline)}</span>
                        {getDaysBadge(inv.lien_days_remaining)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Button 
                      size="sm" 
                      className="bg-primary hover:bg-primary/90 text-primary-foreground h-8"
                      onClick={() => handleSaveToProjects(inv)}
                    >
                      <Save className="h-3.5 w-3.5 mr-1.5" />
                      Save
                    </Button>
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
