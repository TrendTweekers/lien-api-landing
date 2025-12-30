import { useState } from "react";
import { DollarSign, TrendingUp, Users, ArrowRight, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const benefits = [
  {
    icon: DollarSign,
    title: "$500 Per Referral",
    description: "Earn a one-time bounty for every client you bring on board.",
  },
  {
    icon: TrendingUp,
    title: "$50/Month Recurring",
    description: "Or choose 15% recurring revenue share for ongoing income.",
  },
  {
    icon: Users,
    title: "Add Value to Clients",
    description: "Help your construction clients protect their receivables.",
  },
];

export const PartnerProgram = () => {
  const [paymentModel, setPaymentModel] = useState<"recurring" | "bounty">("recurring");
  const [clientCount, setClientCount] = useState(100);

  const monthlyEarnings = paymentModel === "recurring" ? clientCount * 50 : clientCount * 500;
  const annualProjection = paymentModel === "recurring" ? monthlyEarnings * 12 : monthlyEarnings;

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
            and earn up to $180K MRR in recurring commissions.
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
            onClick={() => window.location.href = '/partners.html'}
          >
            Join Partner Program
            <ArrowRight className="h-5 w-5 ml-2" />
          </Button>
        </div>

        {/* Right Side - Calculator */}
        <div className="bg-gray-800/50 p-8 lg:p-10">
          <p className="text-gray-400 mb-2">Partners choose their preferred payment model</p>
          
          <h3 className="text-xl font-bold text-white mb-1">Choose Your Partner Payment Model</h3>
          <p className="text-gray-500 text-sm mb-6">
            Select ONE model - you cannot earn both for the same client
          </p>

          {/* Toggle Buttons */}
          <div className="grid grid-cols-2 gap-2 mb-8">
            <button
              onClick={() => setPaymentModel("recurring")}
              className={`py-3 px-4 rounded-lg font-semibold transition-all ${
                paymentModel === "recurring"
                  ? "bg-primary text-primary-foreground"
                  : "bg-gray-700/50 text-gray-400 hover:bg-gray-700"
              }`}
            >
              Recurring Revenue
            </button>
            <button
              onClick={() => setPaymentModel("bounty")}
              className={`py-3 px-4 rounded-lg font-semibold transition-all ${
                paymentModel === "bounty"
                  ? "bg-primary text-primary-foreground"
                  : "bg-gray-700/50 text-gray-400 hover:bg-gray-700"
              }`}
            >
              Upfront Bounty
            </button>
          </div>

          {/* Model Details */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Coins className="h-5 w-5 text-primary" />
              <h4 className="font-bold text-white underline decoration-primary/50 underline-offset-2">
                {paymentModel === "recurring" ? "Recurring Revenue Model" : "Upfront Bounty Model"}
              </h4>
            </div>
            
            <ul className="space-y-1 text-gray-400 text-sm">
              {paymentModel === "recurring" ? (
                <>
                  <li>• Earn $50/month for EVERY active client</li>
                  <li>• Works for both monthly ($299) and annual ($2,390) subscribers</li>
                  <li>• Get paid monthly as long as clients remain active</li>
                </>
              ) : (
                <>
                  <li>• Earn $500 one-time for EVERY client you refer</li>
                  <li>• Get paid upfront when client subscribes</li>
                  <li>• No ongoing tracking needed</li>
                </>
              )}
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
                <span className="text-gray-400">
                  {paymentModel === "recurring" ? "Monthly earnings:" : "Total earnings:"}
                </span>
                <span className="text-primary font-semibold">
                  {clientCount} × ${paymentModel === "recurring" ? "50" : "500"} = ${monthlyEarnings.toLocaleString()}
                  {paymentModel === "recurring" && "/month"}
                </span>
              </div>
              
              {paymentModel === "recurring" && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Annual projection:</span>
                  <span className="text-primary font-semibold">
                    {clientCount} × $50 × 12 = ${annualProjection.toLocaleString()}/year
                  </span>
                </div>
              )}
            </div>
          </div>

          <p className="text-gray-500 text-xs mt-4 italic">
            Note: Partners select ONE payment model when they join the program. You cannot earn both the bounty and
            recurring revenue for the same client.
          </p>
        </div>
      </div>
    </div>
  );
};
