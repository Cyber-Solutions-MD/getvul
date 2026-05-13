import { notFound } from 'next/navigation';
import Link from 'next/link';
import { Bell, Plus, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SsoButton } from '@/components/ui/sso-button';
import { GradientText } from '@/components/ui/gradient-text';

export default function DevPrimitivesPage() {
  // D-31 + Open Question 6: production builds 404 via notFound() at the top of the
  // page. Simpler than manifest tricks; route exists in build output but short-circuits
  // before rendering any primitive surface.
  if (process.env.NODE_ENV === 'production') {
    notFound();
  }

  return (
    <main className="min-h-screen bg-bg text-text p-12 font-sans">
      <header className="mb-12">
        <h1 className="text-3xl font-bold mb-2">
          <GradientText>Primitives</GradientText> — dev only
        </h1>
        <p className="text-text-muted text-sm">
          NODE_ENV gate at top of page returns 404 in production builds. State matrix
          per D-31; replaces the out-of-scope Storybook playground.
        </p>
      </header>

      <Section title="Button — variants">
        <Row>
          <Button variant="cta">Start triage</Button>
          <Button variant="secondary">Snooze 1h</Button>
          <Button variant="ghost">View trace</Button>
          <Button variant="icon" aria-label="Notifications">
            <Bell className="h-4 w-4" aria-hidden />
          </Button>
        </Row>
      </Section>

      <Section title="Button — sizes (secondary)">
        <Row>
          <Button size="sm">Small</Button>
          <Button size="md">Medium</Button>
          <Button size="lg">Large</Button>
        </Row>
      </Section>

      <Section title="Button — states">
        <Row>
          <Button>Default</Button>
          <Button disabled>Disabled</Button>
          <Button loading loadingText="Signing in…">
            Sign in
          </Button>
          <Button leftIcon={<Plus className="h-4 w-4" aria-hidden />}>Left icon</Button>
          <Button rightIcon={<ChevronDown className="h-4 w-4" aria-hidden />}>
            Right icon
          </Button>
        </Row>
      </Section>

      <Section title="Button — asChild (renders as anchor)">
        <Row>
          <Button asChild variant="cta">
            <Link href="/dashboard">Go to dashboard</Link>
          </Button>
        </Row>
      </Section>

      <Section title="Input — types and states">
        <div className="grid grid-cols-2 gap-4 max-w-xl">
          <label className="block text-sm">
            <span className="block mb-1 text-text-muted">Email</span>
            <Input type="email" placeholder="you@company.com" />
          </label>
          <label className="block text-sm">
            <span className="block mb-1 text-text-muted">Password (eye-toggle)</span>
            <Input type="password" defaultValue="hunter2" />
          </label>
          <label className="block text-sm">
            <span className="block mb-1 text-text-muted">Error state</span>
            <Input type="email" defaultValue="bad@" aria-invalid="true" />
          </label>
          <label className="block text-sm">
            <span className="block mb-1 text-text-muted">Disabled</span>
            <Input type="text" disabled defaultValue="locked" />
          </label>
        </div>
      </Section>

      <Section title="SsoButton — providers">
        <div className="grid grid-cols-1 gap-3 max-w-sm">
          <SsoButton provider="google" />
          <SsoButton provider="microsoft" />
        </div>
      </Section>

      <Section title="GradientText — accent slot">
        <p className="text-2xl font-bold leading-snug">
          See your security posture{' '}
          <GradientText>without opening another tool.</GradientText>
        </p>
      </Section>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="text-sm font-medium uppercase tracking-wide text-text-faint mb-3">
        {title}
      </h2>
      <div className="rounded-lg border border-border bg-surface p-6">{children}</div>
    </section>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>;
}
