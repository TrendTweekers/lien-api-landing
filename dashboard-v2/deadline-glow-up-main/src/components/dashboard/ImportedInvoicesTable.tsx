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
}

export const ImportedInvoicesTable = () => {
  const { toast } = useToast();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);

  const calculateDeadlines = (invoiceDateStr: string, type: "Commercial" | "Residential") => {
    const invoiceDate = new Date(invoiceDateStr);
    const year = invoiceDate.getFullYear();
    const month = invoiceDate.getMonth(); // 0-indexed

    let prelimDate: Date;
    let lienDate: Date;

    // Logic based on Standard Texas Rules (matching backend api/calculators.py)
    // Commercial: Prelim (15th of 3rd month), Lien (15th of 4th month)
    // Residential: Prelim (15th of 2nd month), Lien (15th of 3rd month)
    // Note: JS Month is 0-indexed.
    // +1 month = next month (2nd month)
    // +2 months = month after next (3rd month)
    
    if (type === "Commercial") {
      // Prelim: 15th of 3rd month (Month + 2)
      prelimDate = new Date(year, month + 2, 15);
      // Lien: 15th of 4th month (Month + 3)
      lienDate = new Date(year, month + 3, 15);
    } else {
      // Residential
      // Prelim: 15th of 2nd month (Month + 1)
      prelimDate = new Date(year, month + 1, 15);
      // Lien: 15th of 3rd month (Month + 2)
      lienDate = new Date(year, month + 2, 15);
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
        const newDeadlines = calculateDeadlines(inv.date, newType);
        return {
          ...inv,
          project_type: newType,
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
        project_type: "Commercial" 
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
