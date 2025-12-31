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
}

export const ImportedInvoicesTable = () => {
  const { toast } = useToast();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);

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
      setInvoices(invoicesList);
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
              <TableHead className="text-foreground font-semibold">Prelim Deadline</TableHead>
              <TableHead className="text-foreground font-semibold">Lien Deadline</TableHead>
              <TableHead className="text-foreground font-semibold">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
               <TableRow>
                 <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">Loading invoices...</TableCell>
               </TableRow>
            ) : (!invoices || invoices.length === 0) ? (
               <TableRow>
                 <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">No invoices found in the last 90 days.</TableCell>
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
                    <Badge variant={inv.status === "Paid" ? "default" : "secondary"} 
                        className={inv.status === "Paid" ? "bg-success/15 text-success border-success/30" : "bg-muted text-muted-foreground"}>
                        {inv.status === "Paid" ? "Paid" : "Imported"}
                    </Badge>
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
