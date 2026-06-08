import { MessagesSquare } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-foreground p-12 text-background lg:flex">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <MessagesSquare className="h-5 w-5" />
          </span>
          <span className="font-display text-xl font-semibold">EmberChat</span>
        </div>
        <div className="relative z-10 max-w-md space-y-4">
          <h2 className="font-display text-4xl font-semibold leading-tight">
            Answers your customers can trust.
          </h2>
          <p className="text-background/70">
            Train chatbots on your documents and crawled pages. Every reply is grounded
            in your knowledge base, with sources — never invented.
          </p>
        </div>
        <p className="text-sm text-background/50">Multi-tenant · RAG · Streaming</p>
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-primary/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-10 h-80 w-80 rounded-full bg-primary/20 blur-3xl" />
      </div>
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm animate-fade-up">{children}</div>
      </div>
    </div>
  );
}
