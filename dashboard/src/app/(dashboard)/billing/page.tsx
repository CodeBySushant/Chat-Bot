"use client";
import { CreditCard, Check } from "lucide-react";
import { useBilling } from "@/hooks/use-billing";
import { PageHeader } from "@/components/dashboard/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const PLANS = [
  { name: "Starter", price: 0, features: ["1 chatbot", "100 documents", "1k messages / mo", "Community support"] },
  { name: "Growth", price: 49, features: ["5 chatbots", "5k documents", "25k messages / mo", "Website crawling", "Email support"] },
  { name: "Scale", price: 199, features: ["Unlimited chatbots", "Unlimited documents", "250k messages / mo", "Priority support", "SSO & audit logs"] },
];

export default function BillingPage() {
  const { plan, backendPending } = useBilling();

  return (
    <>
      <PageHeader title="Billing" description="Manage your subscription and usage."
        action={backendPending ? <Badge variant="muted">Billing API coming soon</Badge> : undefined} />

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2"><CreditCard className="h-5 w-5 text-primary" />Current plan</CardTitle>
            <Badge>{plan.name}</Badge>
          </div>
          <CardDescription>You are on the {plan.name} plan — ${plan.price}/{plan.interval}.</CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {PLANS.map((p) => {
          const current = p.name === plan.name;
          return (
            <Card key={p.name} className={current ? "border-primary/50 ring-1 ring-primary/20" : ""}>
              <CardHeader>
                <CardTitle className="flex items-baseline justify-between">
                  {p.name}
                  <span className="font-display text-2xl">${p.price}<span className="text-sm font-normal text-muted-foreground">/mo</span></span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <ul className="space-y-2 text-sm">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-success" />{f}</li>
                  ))}
                </ul>
                <Button className="w-full" variant={current ? "outline" : "default"} disabled={current || backendPending}>
                  {current ? "Current plan" : "Upgrade"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Plans are illustrative. Subscription management and metered usage will activate once the
        billing API and payment provider are connected.
      </p>
    </>
  );
}
