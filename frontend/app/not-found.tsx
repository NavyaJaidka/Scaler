import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="glass-card w-full max-w-md rounded-2xl p-6 text-center">
        <p className="text-sm font-semibold text-gray-900">Page not found</p>
        <p className="mt-2 text-sm text-gray-600">
          The chat is available from the home page.
        </p>
        <Link
          href="/"
          className="mt-4 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Back to chat
        </Link>
      </div>
    </main>
  );
}
