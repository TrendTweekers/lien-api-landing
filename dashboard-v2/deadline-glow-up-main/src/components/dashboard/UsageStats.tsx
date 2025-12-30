import { BarChart3, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const statesUsed = ["TX", "CA", "FL"];

export const UsageStats = () => {
  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-info/15 flex items-center justify-center">
          <BarChart3 className="h-5 w-5 text-info" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">Usage This Month</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <p className="text-sm text-muted-foreground mb-2">Total API Calls</p>
          <p className="text-4xl font-bold text-primary">1,247</p>
          <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
        </div>

        <div>
          <p className="text-sm text-muted-foreground mb-2 flex items-center gap-1">
            <MapPin className="h-4 w-4" />
            States Used
          </p>
          <div className="flex flex-wrap gap-2">
            {statesUsed.map((state) => (
              <Badge
                key={state}
                variant="outline"
                className="bg-muted border-border text-foreground px-3 py-1 font-medium"
              >
                {state}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
