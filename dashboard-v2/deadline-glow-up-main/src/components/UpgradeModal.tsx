import { X, Check } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface UpgradeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Stripe payment links
const STRIPE_LINKS = {
  basic_monthly: "https://buy.stripe.com/8x23cv2KV0WZc7fdfD9fW02",
  basic_annual: "https://buy.stripe.com/5kQ4gzgBL7lngnvejH9fW03",
  automated_monthly: "https://buy.stripe.com/aFa9ATdpz7ln4EN8Zn9fW04",
  automated_annual: "https://buy.stripe.com/eVqdR9etD0WZefncbz9fW05",
};

const PRICING_TIERS = [
  {
    name: "Basic Tracker",
    price: "$49",
    period: "/month",
    annualPrice: "$39/month",
    features: [
      "Unlimited calculations",
      "Email reminders (7 & 1 day)",
      "PDF state guides",
      "Basic reporting",
      "Priority email support",
    ],
    cta: "Start Basic",
    planId: "basic",
    highlight: false,
    stripeMonthly: STRIPE_LINKS.basic_monthly,
    stripeAnnual: STRIPE_LINKS.basic_annual,
  },
  {
    name: "Automated Compliance",
    price: "$149",
    period: "/month",
    annualPrice: "$129/month",
    features: [
      "Zapier included (6,000+ apps)",
      "Multi-channel alerts (Slack, SMS, Calendar)",
      "Team collaboration (3 users)",
      "API access (500 calls/month)",
      "Advanced reporting",
      "Monthly law updates",
    ],
    cta: "Start Automated",
    planId: "automated",
    highlight: true,
    stripeMonthly: STRIPE_LINKS.automated_monthly,
    stripeAnnual: STRIPE_LINKS.automated_annual,
  },
  {
    name: "Enterprise & Partners",
    price: "$499",
    period: "/month",
    annualPrice: "Custom annual pricing",
    features: [
      "Everything in Automated",
      "White-label for partners",
      "Custom integrations",
      "Dedicated account manager",
      "Unlimited API calls",
      "SLA guarantee",
    ],
    cta: "Contact Sales",
    planId: "enterprise",
    highlight: false,
  },
];

export const UpgradeModal = ({ open, onOpenChange }: UpgradeModalProps) => {
  const [toltReferralId, setToltReferralId] = useState<string | null>(null);

  useEffect(() => {
    // Get Tolt referral ID: prioritize 'via' URL parameter, then window.tolt_referral, then sessionStorage
    const urlParams = new URLSearchParams(window.location.search);
    const viaParam = urlParams.get('via');
    const referralId = viaParam || (window as any).tolt_referral || sessionStorage.getItem('tolt_referral') || null;
    setToltReferralId(referralId);
    
    // Persist via param to sessionStorage if present
    if (viaParam) {
      sessionStorage.setItem('tolt_referral', viaParam);
    }
  }, []);

  const handleUpgrade = (planId: string, isAnnual: boolean = false) => {
    if (planId === "enterprise") {
      window.open("/contact", "_blank");
      onOpenChange(false);
      return;
    }

    const tier = PRICING_TIERS.find(t => t.planId === planId);
    if (!tier || !tier.stripeMonthly) {
      // Fallback to signup page
      window.open(`/signup?plan=${planId}`, "_blank");
      onOpenChange(false);
      return;
    }

    // Build Stripe payment link with Tolt referral tracking
    const stripeLink = isAnnual ? tier.stripeAnnual : tier.stripeMonthly;
    const url = new URL(stripeLink);
    
    if (toltReferralId) {
      url.searchParams.append('client_reference_id', toltReferralId);
    }
    
    window.open(url.toString(), "_blank");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-2xl">Upgrade Your Plan</DialogTitle>
          <DialogDescription>
            Choose the plan that fits your needs. All plans include calculations for all 50 states + DC.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          {PRICING_TIERS.map((tier) => (
            <div
              key={tier.planId}
              className={`relative rounded-lg border p-6 ${
                tier.highlight
                  ? "border-primary bg-primary/5 shadow-lg"
                  : "border-border bg-card"
              }`}
            >
              {tier.highlight && (
                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground">
                  MOST POPULAR
                </Badge>
              )}
              
              <h3 className="text-xl font-bold mb-2">{tier.name}</h3>
              
              <div className="mb-4">
                <span className="text-3xl font-bold">{tier.price}</span>
                <span className="text-muted-foreground">{tier.period}</span>
                <p className="text-sm text-muted-foreground mt-1">{tier.annualPrice}</p>
              </div>

              <ul className="space-y-2 mb-6">
                {tier.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <Check className="h-4 w-4 text-success mt-0.5 flex-shrink-0" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <div className="space-y-2">
                <Button
                  className={`w-full ${
                    tier.highlight
                      ? "bg-primary hover:bg-primary/90"
                      : "bg-secondary hover:bg-secondary/90"
                  }`}
                  onClick={() => handleUpgrade(tier.planId, false)}
                >
                  {tier.cta} (Monthly)
                </Button>
                {tier.planId !== "enterprise" && (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => handleUpgrade(tier.planId, true)}
                  >
                    {tier.cta} (Annual - Save 20%)
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>Annual plans save 20%. All plans include calculations for all 50 states + DC.</p>
        </div>
      </DialogContent>
    </Dialog>
  );
};

