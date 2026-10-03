export const money = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
export const label = (s: string) =>
  s
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());
export function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status.toLowerCase()}>
      <span className="status-dot" />
      {label(status)}
    </span>
  );
}
export function Progress({ value }: { value: number }) {
  return (
    <div className="score-inline">
      <div className="bar">
        <span style={{ width: value + "%" }} />
      </div>
      <strong>{value}%</strong>
    </div>
  );
}
