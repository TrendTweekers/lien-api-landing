import { useState } from "react";
import { Key, Eye, EyeOff, Copy, RefreshCw, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export const ApiKeySection = () => {
  const [revealed, setRevealed] = useState(false);
  const apiKey = "sk_live_1a2b...7g8h";
  const fullApiKey = "sk_live_1a2b3c4d5e6f7g8h";

  const handleCopy = () => {
    navigator.clipboard.writeText(fullApiKey);
    toast.success("API key copied to clipboard");
  };

  const handleRegenerate = () => {
    toast.info("API key regeneration would happen here");
  };

  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-warning/15 flex items-center justify-center">
          <Key className="h-5 w-5 text-warning" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-foreground">Your API Key</h2>
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Shield className="h-3 w-3" />
            Keep your API key secret. Never share it publicly.
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <Input
            type={revealed ? "text" : "password"}
            value={revealed ? fullApiKey : apiKey}
            readOnly
            className="bg-muted border-border font-mono pr-10"
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setRevealed(!revealed)}
            className="border-border hover:bg-muted"
          >
            {revealed ? <EyeOff className="h-4 w-4 mr-1.5" /> : <Eye className="h-4 w-4 mr-1.5" />}
            {revealed ? "Hide" : "Reveal"}
          </Button>
          <Button
            variant="outline"
            onClick={handleCopy}
            className="border-border hover:bg-muted"
          >
            <Copy className="h-4 w-4 mr-1.5" />
            Copy
          </Button>
          <Button
            onClick={handleRegenerate}
            className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
          >
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Regenerate
          </Button>
        </div>
      </div>
    </div>
  );
};
