export function fmtBytes(n: number | null | undefined) {
  if (!n && n !== 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function relativeTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const ms = new Date(iso).getTime() - Date.now();
  const abs = Math.abs(ms);
  const mins = Math.round(abs / 60000);
  const hrs = Math.round(mins / 60);
  const suffix = ms < 0 ? "ago" : "from now";
  if (mins < 60) return `${mins} min ${suffix}`;
  if (hrs < 24) return `${hrs} hr ${suffix}`;
  return `${Math.round(hrs / 24)} d ${suffix}`;
}

export function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}
