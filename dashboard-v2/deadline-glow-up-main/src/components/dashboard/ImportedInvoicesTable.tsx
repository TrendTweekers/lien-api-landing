import { useState, useEffect } from "react";
import { RefreshCw, Save } from "lucide-react";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

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

export const ImportedInvoicesTable = () => {
  const { toast } = useToast();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);

  const calculateDeadlines = (invoiceDateStr: string, type: "Commercial" | "Residential", state: string) => {
    const invoiceDate = new Date(invoiceDateStr);
    const year = invoiceDate.getFullYear();
    const month = invoiceDate.getMonth(); // 0-indexed

    let prelimDate: Date;
    let lienDate: Date;

    // Logic based on State Rules
    if (state === "TX") {
      // Standard Texas Rules
      // Commercial: Prelim (15th of 3rd month), Lien (15th of 4th month)
      // Residential: Prelim (15th of 2nd month), Lien (15th of 3rd month)
      if (type === "Commercial") {
        prelimDate = new Date(year, month + 2, 15);
        lienDate = new Date(year, month + 3, 15);
      } else {
        prelimDate = new Date(year, month + 1, 15);
        lienDate = new Date(year, month + 2, 15);
      }
    } else if (state === "CA" || state === "FL") {
      // California & Florida (Simplified: 90 days from Invoice Date)
      // Note: Real rules are more complex (e.g. CA is 20 days prelim, 90 days lien from completion)
      // But for this demo/requirement: 90 days from invoice.
      const date90 = new Date(invoiceDate);
      date90.setDate(date90.getDate() + 90);
      
      prelimDate = date90; // Using same date for simplicity or maybe prelim should be earlier? 
      // User said: "90 days from Invoice Date" for CA/FL. 
      // Usually this refers to Lien deadline. 
      // For Prelim, CA is 20 days. But user instructions were "CA: 90 days... FL: 90 days...".
      // Let's assume 90 days is the Lien Deadline.
      // For Prelim, let's just set it to 20 days for CA/FL as a reasonable default if not specified, 
      // or just make them both 90 if that's the "simplified rule".
      // Let's stick to the user's specific text: "90 days from Invoice Date (Simplified rule for demo)."
      lienDate = date90;
      
      // Setting prelim to same or slightly earlier to avoid nulls. 
      // Let's say 20 days for Prelim (common in many states)
      const date20 = new Date(invoiceDate);
      date20.setDate(date20.getDate() + 20);
      prelimDate = date20;
    } else {
      // Default / Other States: 90 Day Rule
      const date90 = new Date(invoiceDate);
      date90.setDate(date90.getDate() + 90);
      lienDate = date90;
      
      const date20 = new Date(invoiceDate);
      date20.setDate(date20.getDate() + 20);
      prelimDate = date20;
    }

    const today = new Date();
    const prelimDays = Math.ceil((prelimDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    const lienDays = Math.ceil((lienDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

    return {
      preliminary_deadline: prelimDate.toISOString(),
      lien_deadline: lienDate.toISOString(),
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

  const handleSaveToProjects = (invoice: Invoice) => {
    console.log("Saving to projects:", invoice);
    toast({
      title: "Saved to Projects",
      description: `Invoice #${invoice.invoice_number} saved as ${invoice.project_type}.`,
    });
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
      const processedList = invoicesList.map((inv: any) => ({
        ...inv,
        project_type: "Commercial",
        project_state: "TX" // Default to Texas
      }));

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
              <TableHead className="text-foreground font-semibold">Date</TableHead>
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
