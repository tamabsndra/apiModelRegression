export function OperatorDashboard({ onLoggedOut }: { onLoggedOut: () => void }) {
  return (
    <div className="p-10">
      dashboard
      <button type="button" onClick={onLoggedOut}>keluar</button>
    </div>
  );
}