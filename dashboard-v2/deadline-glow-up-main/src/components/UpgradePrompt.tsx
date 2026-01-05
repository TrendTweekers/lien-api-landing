import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface UpgradePromptProps {
  calculationsUsed: number;
  calculationsLimit: number;
}

export default function UpgradePrompt({ calculationsUsed, calculationsLimit }: UpgradePromptProps) {
  if (calculationsUsed < calculationsLimit) return null;
  
  return (
    <Alert className="bg-orange-50 border-l-4 border-orange-500 mb-6">
      <AlertTriangle className="h-6 w-6 text-orange-500" />
      <AlertTitle className="text-lg font-semibold text-orange-900">
        Free Trial Limit Reached
      </AlertTitle>
      <AlertDescription className="text-orange-700 mt-1">
        <p>
          You've used all {calculationsLimit} free calculations. 
          Upgrade to Professional for unlimited calculations and premium features.
        </p>
        <a 
          href="/pricing.html" 
          className="inline-block mt-3"
        >
          <Button className="bg-orange-500 hover:bg-orange-600 text-white">
            Upgrade Now
          </Button>
        </a>
      </AlertDescription>
    </Alert>
  );
}

