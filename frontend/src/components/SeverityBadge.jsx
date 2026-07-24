export default function SeverityBadge({ severity }) {
  const s = severity || "P4";
  const styles = {
    P1: "bg-ll-danger text-white animate-pulse",
    P2: "bg-orange-600 text-white",
    P3: "bg-ll-warn text-black",
    P4: "bg-ll-accent text-black",
  };
  return (
    <span
      className={`inline-flex items-center rounded-md px-2.5 py-0.5 font-mono text-xs font-semibold ${styles[s] || styles.P4}`}
    >
      {s}
    </span>
  );
}
