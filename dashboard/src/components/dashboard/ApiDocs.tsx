import { BookOpen, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export const ApiDocs = () => {
  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
          <BookOpen className="h-5 w-5 text-foreground" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-foreground">API Documentation</h2>
          <p className="text-sm text-muted-foreground">Learn how to integrate our API into your application.</p>
        </div>
      </div>

      <Button variant="outline" className="border-border hover:bg-muted hover:border-primary group">
        View API Docs
        <ArrowRight className="h-4 w-4 ml-2 group-hover:translate-x-1 transition-transform" />
      </Button>
    </div>
  );
};
