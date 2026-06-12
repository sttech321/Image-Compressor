/** Backend API origin for server-side proxy (runtime env on Render). */
export function backendOrigin(): string {
  const raw =
    process.env.API_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) {
    return 'http://localhost:5000';
  }
  const trimmed = raw.replace(/\/$/, '');
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}
