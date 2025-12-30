import { CreditCard, Calendar, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export const BillingSection = () => {
  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <CreditCard className="h-5 w-5 text-primary" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">Billing</h2>
        </div>
        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground">
          Manage Billing
        </Button>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current Plan</p>
            <p className="font-semibold text-foreground">$299/month (Unlimited)</p>
          </div>
        </div>

        <Separator className="bg-border" />

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Payment Method</p>
            <p className="font-semibold text-foreground flex items-center gap-2">
              <span className="inline-flex w-8 h-5 bg-info rounded text-xs text-info-foreground items-center justify-center font-bold">VISA</span>
              •••• 4242
            </p>
          </div>
          <Button variant="link" className="text-primary p-0 h-auto font-medium">
            Update
          </Button>
        </div>

        <Separator className="bg-border" />

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Next Charge</p>
            <p className="font-semibold text-foreground flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              $299 on Dec 23, 2025
            </p>
          </div>
        </div>

        <button className="flex items-center gap-1 text-sm text-primary hover:text-primary/80 transition-colors mt-2 font-medium">
          View Invoices
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
