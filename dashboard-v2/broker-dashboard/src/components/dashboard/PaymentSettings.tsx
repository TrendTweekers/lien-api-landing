import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

interface PaymentSettingsProps {
  email: string;
}

export const PaymentSettings = ({ email }: PaymentSettingsProps) => {
  const [loading, setLoading] = useState(false);
  const [method, setMethod] = useState("paypal");
  const [formData, setFormData] = useState({
    payment_email: "",
    bank_name: "",
    account_holder_name: "",
    iban: "",
    swift_code: "",
    bank_address: "",
    crypto_wallet: "",
    crypto_currency: "USDT",
    tax_id: ""
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.id]: e.target.value });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const token = localStorage.getItem("broker_token");
      const res = await fetch("/api/v1/broker/payment-info", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          email,
          payment_method: method,
          ...formData
        })
      });

      const data = await res.json();
      if (res.ok) {
        toast.success("Payment information saved");
      } else {
        toast.error(data.message || "Failed to save");
      }
    } catch (error) {
      toast.error("An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Payment Settings</CardTitle>
        <CardDescription>How would you like to receive your commissions?</CardDescription>
      </CardHeader>
      <form onSubmit={handleSave}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Payment Method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="paypal">PayPal</SelectItem>
                <SelectItem value="bank_transfer">Bank Transfer (Wire)</SelectItem>
                <SelectItem value="crypto">Crypto (USDT/BTC)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {method === "paypal" && (
            <div className="space-y-2">
              <Label htmlFor="payment_email">PayPal Email</Label>
              <Input id="payment_email" value={formData.payment_email} onChange={handleChange} placeholder="email@example.com" />
            </div>
          )}

          {method === "bank_transfer" && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="account_holder_name">Account Holder Name</Label>
                  <Input id="account_holder_name" value={formData.account_holder_name} onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="bank_name">Bank Name</Label>
                  <Input id="bank_name" value={formData.bank_name} onChange={handleChange} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="iban">IBAN / Account Number</Label>
                  <Input id="iban" value={formData.iban} onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="swift_code">SWIFT / BIC / Routing</Label>
                  <Input id="swift_code" value={formData.swift_code} onChange={handleChange} />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="bank_address">Bank Address</Label>
                <Input id="bank_address" value={formData.bank_address} onChange={handleChange} />
              </div>
            </>
          )}

          {method === "crypto" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="crypto_currency">Currency</Label>
                <Input id="crypto_currency" value={formData.crypto_currency} onChange={handleChange} placeholder="USDT (TRC20)" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="crypto_wallet">Wallet Address</Label>
                <Input id="crypto_wallet" value={formData.crypto_wallet} onChange={handleChange} />
              </div>
            </>
          )}
          
          <div className="pt-4 border-t">
            <div className="space-y-2">
              <Label htmlFor="tax_id">Tax ID / SSN (Optional)</Label>
              <Input id="tax_id" value={formData.tax_id} onChange={handleChange} placeholder="For tax reporting purposes" />
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <Button type="submit" disabled={loading}>
            {loading ? "Saving..." : "Save Changes"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
};
