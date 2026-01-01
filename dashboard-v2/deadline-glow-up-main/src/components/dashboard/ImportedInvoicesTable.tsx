import { useState, useEffect } from "react";
import { RefreshCw } from "lucide-react";
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

const US_STATES = [
  { name: "Alabama", code: "AL" },
  { name: "Alaska", code: "AK" },
  { name: "Arizona", code: "AZ" },
  { name: "Arkansas", code: "AR" },
  { name: "California", code: "CA" },
  { name: "Colorado", code: "CO" },
  { name: "Connecticut", code: "CT" },
  { name: "Delaware", code: "DE" },
  { name: "Florida", code: "FL" },
  { name: "Georgia", code: "GA" },
  { name: "Hawaii", code: "HI" },
  { name: "Idaho", code: "ID" },
  { name: "Illinois", code: "IL" },
  { name: "Indiana", code: "IN" },
  { name: "Iowa", code: "IA" },
  { name: "Kansas", code: "KS" },
  { name: "Kentucky", code: "KY" },
  { name: "Louisiana", code: "LA" },
  { name: "Maine", code: "ME" },
  { name: "Maryland", code: "MD" },
  { name: "Massachusetts", code: "MA" },
  { name: "Michigan", code: "MI" },
  { name: "Minnesota", code: "MN" },
  { name: "Mississippi", code: "MS" },
  { name: "Missouri", code: "MO" },
  { name: "Montana", code: "MT" },
  { name: "Nebraska", code: "NE" },
  { name: "Nevada", code: "NV" },
  { name: "New Hampshire", code: "NH" },
  { name: "New Jersey", code: "NJ" },
  { name: "New Mexico", code: "NM" },
  { name: "New York", code: "NY" },
  { name: "North Carolina", code: "NC" },
  { name: "North Dakota", code: "ND" },
  { name: "Ohio", code: "OH" },
  { name: "Oklahoma", code: "OK" },
  { name: "Oregon", code: "OR" },
  { name: "Pennsylvania", code: "PA" },
  { name: "Rhode Island", code: "RI" },
  { name: "South Carolina", code: "SC" },
  { name: "South Dakota", code: "SD" },
  { name: "Tennessee", code: "TN" },
  { name: "Texas", code: "TX" },
  { name: "Utah", code: "UT" },
  { name: "Vermont", code: "VT" },
  { name: "Virginia", code: "VA" },
  { name: "Washington", code: "WA" },
  { name: "West Virginia", code: "WV" },
  { name: "Wisconsin", code: "WI" },
  { name: "Wyoming", code: "WY" },
];

interface Invoice {
  id: string;
  invoice_number: string;
  customer_name: string;
  date: string;
  amount: number;
  balance: number;
  status: string;
  is_saved?: boolean;  // Indicates if invoice has been saved as a project
  state: string;
  preliminary_deadline: string | null;
  lien_deadline: string | null;
  prelim_days_remaining: number | null;
  lien_days_remaining: number | null;
}

export const ImportedInvoicesTable = ({ isConnected = false, isChecking = false }: { isConnected?: boolean; isChecking?: boolean }) => {
  const { toast } = useToast();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  // Track selected state and type for each invoice
  const [invoiceSelections, setInvoiceSelections] = useState<Record<string, { state: string; type: string }>>({});

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/quickbooks/invoices", { headers });
      
      if (res.status === 404) {
        setLoading(false);
        return;
      }

      if (!res.ok) throw new Error("Failed to fetch invoices");
      
      const data = await res.json();
      // API returns { invoices: [...], count: ... }
      const invoiceArray = Array.isArray(data) ? data : (data?.invoices || []);
      setInvoices(invoiceArray);
    } catch (e) {
      console.error(e);
      // Only show error toast if we are connected
      if (isConnected) {
        toast({
            title: "Error",
            description: "Failed to load invoices.",
            variant: "destructive",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isConnected) {
        fetchInvoices();
    }

    // Listen for project deletion events to refresh invoices
    const handleProjectDeleted = () => {
      if (isConnected) {
        fetchInvoices();
      }
    };

    window.addEventListener('project-deleted', handleProjectDeleted);

    return () => {
      window.removeEventListener('project-deleted', handleProjectDeleted);
    };
  }, [isConnected]);

  if (isChecking) {
    return (
       <div className="bg-card rounded-xl overflow-hidden border border-border card-shadow mt-8 animate-slide-up" style={{ animationDelay: "0.22s" }}>
            <div className="p-12 text-center">
                <RefreshCw className="h-8 w-8 animate-spin mx-auto text-primary mb-4" />
                <p className="text-muted-foreground">Checking for connection...</p>
            </div>
       </div>
    );
 }

  if (!isConnected && !loading) return null;

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
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
              <TableHead className="text-foreground font-semibold">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
               <TableRow>
                 <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">Loading invoices...</TableCell>
               </TableRow>
            ) : invoices.length === 0 ? (
               <TableRow>
                 <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">No invoices found in the last 90 days.</TableCell>
               </TableRow>
            ) : (
              invoices.map((inv) => {
                const isSaved = inv.is_saved === true;
                const selection = invoiceSelections[inv.id] || { state: inv.state || "", type: "Commercial" };
                
                return (
                  <TableRow key={inv.id} className="border-border hover:bg-muted/30">
                    <TableCell className="font-medium text-foreground">{inv.invoice_number}</TableCell>
                    <TableCell className="text-foreground">{inv.customer_name}</TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(inv.date)}</TableCell>
                    <TableCell className="font-semibold text-foreground">
                      ${inv.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell>
                      {isSaved ? (
                        <Badge className="bg-muted text-muted-foreground">{inv.state}</Badge>
                      ) : (
                        <Select
                          value={selection.state}
                          onValueChange={(value) => {
                            setInvoiceSelections(prev => ({
                              ...prev,
                              [inv.id]: { ...selection, state: value }
                            }));
                          }}
                        >
                          <SelectTrigger className="w-[140px]">
                            <SelectValue placeholder="Select state" />
                          </SelectTrigger>
                          <SelectContent>
                            {US_STATES.map((state) => (
                              <SelectItem key={state.code} value={state.code}>
                                {state.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    </TableCell>
                    <TableCell>
                      {isSaved ? (
                        <Badge className="bg-muted text-muted-foreground">Commercial</Badge>
                      ) : (
                        <Select
                          value={selection.type}
                          onValueChange={(value) => {
                            setInvoiceSelections(prev => ({
                              ...prev,
                              [inv.id]: { ...selection, type: value }
                            }));
                          }}
                        >
                          <SelectTrigger className="w-[140px]">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Commercial">Commercial</SelectItem>
                            <SelectItem value="Residential">Residential</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
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
                      <Badge 
                        variant={inv.status === "Paid" ? "default" : isSaved ? "secondary" : "default"}
                        className={
                          inv.status === "Paid" 
                            ? "bg-success/15 text-success border-success/30" 
                            : isSaved
                            ? "bg-muted text-muted-foreground"
                            : "bg-primary/15 text-primary border-primary/30"
                        }
                      >
                        {inv.status === "Paid" ? "Paid" : isSaved ? "Imported" : "New"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
