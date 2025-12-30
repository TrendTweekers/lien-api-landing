import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Lock, Eye, EyeOff } from "lucide-react";

interface PaymentSettingsProps {
  email?: string;
}

export const PaymentSettings = ({ email }: PaymentSettingsProps) => {
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  
  const [method, setMethod] = useState("");
  const [formData, setFormData] = useState({
    payment_email: "",
    bank_name: "",
    account_holder_name: "",
    iban: "",
    swift_code: "",
    bank_address: "",
    crypto_wallet: "",
    crypto_currency: "",
    tax_id: ""
  });

  // Load saved data on mount
  useEffect(() => {
    const fetchPaymentInfo = async () => {
      try {
        const token = localStorage.getItem("broker_token");
        const brokerEmail = email || localStorage.getItem("broker_email");
        
        if (!brokerEmail) return;

        const res = await fetch(`/api/v1/broker/payment-info?email=${encodeURIComponent(brokerEmail)}`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        
        const data = await res.json();
        
        if (res.ok && data.status === "success" && data.payment_info) {
          const info = data.payment_info;
          setMethod(info.payment_method || "");
          setFormData({
            payment_email: info.payment_email || "",
            bank_name: info.bank_name || "",
            account_holder_name: info.account_holder_name || "",
            iban: info.iban || "",
            swift_code: info.swift_code || "",
            bank_address: info.bank_address || "",
            crypto_wallet: info.crypto_wallet || "",
            crypto_currency: info.crypto_currency || "",
            tax_id: info.tax_id || ""
          });
        }
      } catch (error) {
        console.error("Failed to load payment info", error);
      } finally {
        setInitialLoading(false);
      }
    };

    fetchPaymentInfo();
  }, [email]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.id]: e.target.value });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const token = localStorage.getItem("broker_token");
      const brokerEmail = email || localStorage.getItem("broker_email");

      const res = await fetch("/api/v1/broker/payment-info", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          email: brokerEmail,
          payment_method: method,
          ...formData
        })
      });

      const data = await res.json();
      if (res.ok) {
        toast.success("Payment information saved");
        setIsEditing(false);
        // Refresh data to show masked values if backend returns them, 
        // or just keep current state. Backend returns success message only.
        // We might want to re-fetch to get the masked values for display security
        // but for UX keeping the entered values is often better until refresh.
        // However, since we toggle view mode, let's re-fetch to be safe and show masked.
        // re-fetch:
        const refetch = await fetch(`/api/v1/broker/payment-info?email=${encodeURIComponent(brokerEmail || "")}`, {
           headers: { "Authorization": `Bearer ${token}` }
        });
        const refreshedData = await refetch.json();
        if (refreshedData.status === "success") {
           const info = refreshedData.payment_info;
           setFormData(prev => ({
             ...prev,
             iban: info.iban || "",
             swift_code: info.swift_code || "",
             crypto_wallet: info.crypto_wallet || "",
             tax_id: info.tax_id || ""
           }));
        }

      } else {
        toast.error(data.message || "Failed to save");
      }
    } catch (error) {
      toast.error("An error occurred");
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <Card>
        <CardContent className="p-8 flex justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  // View Mode
  if (!isEditing) {
    return (
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Payment Settings</CardTitle>
              <CardDescription>How you receive your commissions</CardDescription>
            </div>
            <Button variant="outline" onClick={() => setIsEditing(true)}>Edit Payment Info</Button>
          </div>
        </CardHeader>
        <CardContent>
          {!method ? (
            <div className="text-center py-6 text-muted-foreground">
              No payment information saved.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-muted-foreground">Payment Method</Label>
                  <p className="font-medium capitalize">{method}</p>
                </div>
                
                {(method === "paypal" || method === "wise" || method === "revolut") && (
                  <div>
                    <Label className="text-muted-foreground">Email Address</Label>
                    <p className="font-medium">{formData.payment_email}</p>
                  </div>
                )}

                {(method === "sepa" || method === "swift") && (
                  <>
                    <div>
                      <Label className="text-muted-foreground">Bank Name</Label>
                      <p className="font-medium">{formData.bank_name}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">Account Holder</Label>
                      <p className="font-medium">{formData.account_holder_name}</p>
                    </div>
                    {formData.iban && (
                      <div>
                        <Label className="text-muted-foreground">IBAN / Account</Label>
                        <p className="font-medium font-mono">{formData.iban}</p>
                      </div>
                    )}
                    {formData.swift_code && (
                      <div>
                        <Label className="text-muted-foreground">SWIFT / BIC</Label>
                        <p className="font-medium font-mono">{formData.swift_code}</p>
                      </div>
                    )}
                  </>
                )}

                {method === "crypto" && (
                  <>
                    <div>
                      <Label className="text-muted-foreground">Currency</Label>
                      <p className="font-medium">{formData.crypto_currency}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">Wallet Address</Label>
                      <p className="font-medium font-mono break-all">{formData.crypto_wallet}</p>
                    </div>
                  </>
                )}
              </div>
              
              {formData.tax_id && (
                 <div className="pt-4 border-t">
                    <Label className="text-muted-foreground">Tax ID</Label>
                    <p className="font-medium font-mono">{formData.tax_id}</p>
                 </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // Edit Mode
  return (
    <Card>
      <CardHeader>
        <CardTitle>Update Payment Details</CardTitle>
        <CardDescription>Securely update your payout information</CardDescription>
      </CardHeader>
      <form onSubmit={handleSave}>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label>Payment Method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger>
                <SelectValue placeholder="Select payment method" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="paypal">PayPal</SelectItem>
                <SelectItem value="wise">Wise</SelectItem>
                <SelectItem value="revolut">Revolut</SelectItem>
                <SelectItem value="sepa">SEPA Bank Transfer (EU)</SelectItem>
                <SelectItem value="swift">SWIFT Bank Transfer (International)</SelectItem>
                <SelectItem value="crypto">Cryptocurrency</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Email-based methods */}
          {(method === "paypal" || method === "wise" || method === "revolut") && (
            <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
              <Label htmlFor="payment_email">Payment Email</Label>
              <Input 
                id="payment_email" 
                type="email" 
                value={formData.payment_email} 
                onChange={handleChange} 
                placeholder={`${method}@example.com`}
                required
              />
            </div>
          )}

          {/* Bank Transfer Fields */}
          {(method === "sepa" || method === "swift") && (
            <div className="space-y-4 animate-in fade-in slide-in-from-top-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="account_holder_name">Account Holder Name</Label>
                  <Input 
                    id="account_holder_name" 
                    value={formData.account_holder_name} 
                    onChange={handleChange} 
                    placeholder="Full name on account"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="bank_name">Bank Name</Label>
                  <Input 
                    id="bank_name" 
                    value={formData.bank_name} 
                    onChange={handleChange} 
                    required
                  />
                </div>
              </div>
              
              {method === "sepa" && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="iban">IBAN</Label>
                    <Input 
                      id="iban" 
                      value={formData.iban} 
                      onChange={handleChange} 
                      placeholder="DE00 0000 0000 0000 0000 00"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="swift_code">BIC / SWIFT</Label>
                    <Input 
                      id="swift_code" 
                      value={formData.swift_code} 
                      onChange={handleChange} 
                      required
                    />
                  </div>
                </div>
              )}

              {method === "swift" && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="swift_code">SWIFT Code</Label>
                      <Input 
                        id="swift_code" 
                        value={formData.swift_code} 
                        onChange={handleChange} 
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="iban">Account Number</Label>
                      <Input 
                        id="iban" 
                        value={formData.iban} 
                        onChange={handleChange} 
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="bank_address">Bank Address</Label>
                    <Input 
                      id="bank_address" 
                      value={formData.bank_address} 
                      onChange={handleChange} 
                      placeholder="Full bank branch address"
                      required
                    />
                  </div>
                </>
              )}
            </div>
          )}

          {/* Crypto Fields */}
          {method === "crypto" && (
            <div className="space-y-4 animate-in fade-in slide-in-from-top-2">
              <div className="space-y-2">
                <Label htmlFor="crypto_currency">Currency Type</Label>
                <Select 
                  value={formData.crypto_currency} 
                  onValueChange={(val) => setFormData({...formData, crypto_currency: val})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select currency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="BTC">Bitcoin (BTC)</SelectItem>
                    <SelectItem value="USDT">Tether (USDT - TRC20)</SelectItem>
                    <SelectItem value="ETH">Ethereum (ETH)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="crypto_wallet">Wallet Address</Label>
                <div className="relative">
                  <Input 
                    id="crypto_wallet" 
                    value={formData.crypto_wallet} 
                    onChange={handleChange} 
                    className="font-mono"
                    placeholder="0x..."
                    required
                  />
                  <Lock className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-xs text-muted-foreground">Address is encrypted before storage.</p>
              </div>
            </div>
          )}

          <div className="pt-4 border-t">
            <div className="space-y-2">
              <Label htmlFor="tax_id">Tax ID (Optional)</Label>
              <Input 
                id="tax_id" 
                value={formData.tax_id} 
                onChange={handleChange} 
                placeholder="SSN / EIN / VAT Number" 
              />
              <p className="text-xs text-muted-foreground">Required for annual payouts over $600 USD.</p>
            </div>
          </div>

        </CardContent>
        <CardFooter className="flex gap-2 justify-between">
          <Button type="button" variant="ghost" onClick={() => setIsEditing(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={loading}>
            {loading ? "Saving..." : "Update Payment Information"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
};
