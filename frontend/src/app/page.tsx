export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-950 text-white">
      <h1 className="text-4xl font-bold tracking-tight">GetVul</h1>
      <p className="mt-3 text-lg text-gray-400">
        Unified Vulnerability Aggregation Platform
      </p>
      <div className="mt-8 flex gap-4">
        <a
          href="/login"
          className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium hover:bg-indigo-500 transition"
        >
          Sign In
        </a>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          className="rounded-lg border border-gray-700 px-6 py-2.5 text-sm font-medium hover:border-gray-500 transition"
        >
          API Docs
        </a>
      </div>
    </main>
  );
}
