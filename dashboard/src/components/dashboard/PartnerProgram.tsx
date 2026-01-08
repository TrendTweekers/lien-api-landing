import { useState } from "react";
import { DollarSign, TrendingUp, Users, ArrowRight, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const benefits = [
  {
    icon: TrendingUp,
    title: "30% Monthly Recurring",
    description: "Earn 30% of every subscription payment for as long as clients stay active.",
  },
  {
    icon: DollarSign,
    title: "Passive Income",
    description: "Build long-term recurring revenue helping construction suppliers protect receivables.",
  },
  {
    icon: Users,
    title: "Add Value to Clients",
    description: "Help your construction clients protect their receivables.",
  },
];

export const PartnerProgram = () => {
  const [clientCount, setClientCount] = useState(100);

  // 30% of $149/month Automated subscription = $44.70 per client per month
  const subscriptionPrice = 149; // Automated tier
  const commissionRate = 0.30; // 30%
  const commissionPerClient = subscriptionPrice * commissionRate; // $44.70
  const monthlyEarnings = clientCount * commissionPerClient;
  const annualProjection = monthlyEarnings * 12;

  return (
    <div className="rounded-2xl overflow-hidden bg-gradient-dark card-shadow-lg">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        {/* Left Side - Benefits */}
        <div className="p-8 lg:p-10">
          <p className="text-primary font-semibold text-sm tracking-wide uppercase mb-4">
            Partner Program
          </p>
          
          <h2 className="text-3xl lg:text-4xl font-bold text-white mb-2">
            Earn while helping your clients{" "}
            <span className="italic text-primary">protect receivables</span>
          </h2>
          
          <p className="text-gray-400 mt-4 text-lg">
            Insurance brokers, accountants, and consultants: add LienDeadline to your toolkit
            and earn 30% monthly recurring commission on every referral.
          </p>

          <div className="space-y-6 mt-8">
            {benefits.map((benefit) => (
              <div key={benefit.title} className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-gray-700/50 flex items-center justify-center shrink-0">
                  <benefit.icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-white underline decoration-primary/50 underline-offset-2">
                    {benefit.title}
                  </h3>
                  <p className="text-gray-400 text-sm mt-1">{benefit.description}</p>
                </div>
              </div>
            ))}
          </div>

          <Button 
            className="mt-8 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-6 h-12 text-base"
            onClick={() => window.open('/partners.html', '_blank')}
          >
            Join Partner Program
            <ArrowRight className="h-5 w-5 ml-2" />
          </Button>
        </div>

        {/* Right Side - Calculator */}
        <div className="bg-gray-800/50 p-8 lg:p-10">
          <h3 className="text-xl font-bold text-white mb-1">30% Monthly Recurring Commission</h3>
          <p className="text-gray-500 text-sm mb-6">
            Earn 30% of every subscription payment for as long as your referral stays active
          </p>

          {/* Model Details */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Coins className="h-5 w-5 text-primary" />
              <h4 className="font-bold text-white underline decoration-primary/50 underline-offset-2">
                Commission Structure
              </h4>
            </div>
            
            <ul className="space-y-1 text-gray-400 text-sm">
              <li>• Earn 30% of every $149/month Automated subscription ($44.70 per client)</li>
              <li>• Commission held for 30 days after customer payment to prevent fraud</li>
              <li>• Get paid monthly via direct deposit as long as clients remain active</li>
              <li>• Build long-term passive income with your construction network</li>
            </ul>
          </div>

          {/* Calculator */}
          <div className="bg-gray-900/50 rounded-xl p-5">
            <Label className="text-gray-400 text-sm">Number of clients:</Label>
            <Input
              type="number"
              value={clientCount}
              onChange={(e) => setClientCount(Number(e.target.value) || 0)}
              className="mt-2 bg-gray-800 border-gray-700 text-white text-lg font-medium h-12"
            />

            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Monthly earnings:</span>
                <span className="text-primary font-semibold">
                  {clientCount} × ${commissionPerClient.toFixed(2)} = ${monthlyEarnings.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}/month
                </span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Annual projection:</span>
                <span className="text-primary font-semibold">
                  {clientCount} × ${commissionPerClient.toFixed(2)} × 12 = ${annualProjection.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}/year
                </span>
              </div>
            </div>
          </div>

          <p className="text-gray-500 text-xs mt-4 italic">
            Note: Commission is held for 30 days after customer payment to prevent fraud, then paid monthly via direct deposit.
          </p>
        </div>
      </div>
    </div>
  );
};
