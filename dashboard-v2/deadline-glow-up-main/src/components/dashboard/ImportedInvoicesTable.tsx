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
  // Track which invoices are currently recalculating
  const [recalculatingInvoices, setRecalculatingInvoices] = useState<Set<string>>(new Set());

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
      
      // Initialize selections for unsaved invoices
      const initialSelections: Record<string, { state: string; type: string }> = {};
      invoiceArray.forEach((inv: Invoice) => {
        if (!inv.is_saved && inv.id) {
          initialSelections[inv.id] = {
            state: inv.state || "",
            type: "Commercial"
          };
        }
      });
      setInvoiceSelections(prev => ({ ...prev, ...initialSelections }));
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

  const recalculateDeadlines = async (invoiceId: string, invoiceDate: string, state: string, projectType: string) => {
    if (!state || !invoiceDate) {
      toast({
        title: "Error",
        description: "Please select both State and ensure invoice date is available.",
        variant: "destructive",
      });
      return;
    }

    // Set loading state for this invoice
    setRecalculatingInvoices(prev => new Set(prev).add(invoiceId));

    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch("/api/v1/calculate-deadline", {
        method: "POST",
        headers,
        body: JSON.stringify({
          invoice_date: invoiceDate,
          state: state,
          project_type: projectType,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to recalculate deadlines");
      }

      const data = await response.json();
      
      // Debug: Log the API response to see exact field names
      console.log("🔍 API Response:", data);
      
      // Extract deadline data (handle both wrapped and unwrapped responses)
      const result = data.data || data.result || data;
      
      // Extract preliminary deadline (check multiple possible field names)
      const prelimDeadline = result.prelim_deadline 
        || result.preliminary_notice_deadline 
        || result.prelimDeadline
        || result.preliminaryNoticeDeadline
        || (result.preliminary_notice?.deadline);
      
      // Extract lien deadline (check multiple possible field names including nested)
      const lienDeadline = (result.lien_filing?.deadline)
        || result.lien_deadline 
        || result.lienDeadline
        || result.lien_deadline_str;
      
      // Extract days remaining
      const prelimDays = result.prelim_deadline_days 
        || result.prelimDaysRemaining 
        || result.prelim_days_remaining
        || result.preliminary_days_remaining
        || (result.preliminary_notice?.days_from_now)
        || (result.preliminary_notice?.days_remaining);
      
      const lienDays = result.lien_deadline_days 
        || result.lienDaysRemaining 
        || result.lien_days_remaining
        || (result.lien_filing?.days_from_now)
        || (result.lien_filing?.days_remaining);
      
      // Debug: Log extracted values
      console.log("📅 Extracted deadlines:", {
        prelimDeadline,
        lienDeadline,
        prelimDays,
        lienDays
      });

      // Calculate days remaining from today
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      let prelimDaysRemaining: number | null = null;
      let lienDaysRemaining: number | null = null;

      if (prelimDeadline) {
        const prelimDate = new Date(prelimDeadline);
        prelimDate.setHours(0, 0, 0, 0);
        prelimDaysRemaining = Math.ceil((prelimDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
      }

      if (lienDeadline) {
        const lienDate = new Date(lienDeadline);
        lienDate.setHours(0, 0, 0, 0);
        lienDaysRemaining = Math.ceil((lienDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
      }

      // Update the invoice in the state
      setInvoices(prevInvoices =>
        prevInvoices.map(inv =>
          inv.id === invoiceId
            ? {
                ...inv,
                preliminary_deadline: prelimDeadline || null,
                lien_deadline: lienDeadline || null,
                prelim_days_remaining: prelimDaysRemaining,
                lien_days_remaining: lienDaysRemaining,
                state: state, // Update state as well
              }
            : inv
        )
      );
    } catch (error: any) {
      console.error("Error recalculating deadlines:", error);
      toast({
        title: "Error",
        description: error.message || "Failed to recalculate deadlines. Please try again.",
        variant: "destructive",
      });
    } finally {
      // Remove loading state
      setRecalculatingInvoices(prev => {
        const next = new Set(prev);
        next.delete(invoiceId);
        return next;
      });
    }
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
              <TableHead className="text-foreground font-semibold">PRELIMINARY NOTICE</TableHead>
              <TableHead className="text-foreground font-semibold">LIEN FILING DEADLINE</TableHead>
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
                            const newSelection = { ...selection, state: value };
                            setInvoiceSelections(prev => ({
                              ...prev,
                              [inv.id]: newSelection
                            }));
                            // Recalculate deadlines when state changes
                            if (inv.date && newSelection.type) {
                              recalculateDeadlines(inv.id, inv.date, value, newSelection.type);
                            }
                          }}
                          disabled={recalculatingInvoices.has(inv.id)}
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
                            const newSelection = { ...selection, type: value };
                            setInvoiceSelections(prev => ({
                              ...prev,
                              [inv.id]: newSelection
                            }));
                            // Recalculate deadlines when type changes
                            if (inv.date && newSelection.state) {
                              recalculateDeadlines(inv.id, inv.date, newSelection.state, value);
                            }
                          }}
                          disabled={recalculatingInvoices.has(inv.id)}
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
                      <div className="flex items-center gap-2 p-3 rounded-lg" style={{ backgroundColor: '#d1fae5', border: '1px solid #86efac' }}>
                          {recalculatingInvoices.has(inv.id) ? (
                            <>
                              <RefreshCw className="h-4 w-4 animate-spin text-primary" />
                              <span className="text-muted-foreground text-sm">Calculating...</span>
                            </>
                          ) : (
                            <>
                              <div className="flex flex-col">
                                <span className="text-xs font-semibold text-green-700 mb-1">PRELIMINARY NOTICE</span>
                                <span className="text-foreground font-semibold">{formatDate(inv.preliminary_deadline)}</span>
                                {getDaysBadge(inv.prelim_days_remaining)}
                              </div>
                            </>
                          )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 p-3 rounded-lg" style={{ backgroundColor: '#fed7aa', border: '1px solid #fdba74' }}>
                          {recalculatingInvoices.has(inv.id) ? (
                            <>
                              <RefreshCw className="h-4 w-4 animate-spin text-primary" />
                              <span className="text-muted-foreground text-sm">Calculating...</span>
                            </>
                          ) : (
                            <>
                              <div className="flex flex-col">
                                <span className="text-xs font-semibold text-orange-700 mb-1">LIEN FILING DEADLINE</span>
                                <span className="text-foreground font-semibold">{formatDate(inv.lien_deadline)}</span>
                                {getDaysBadge(inv.lien_days_remaining)}
                              </div>
                            </>
                          )}
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
