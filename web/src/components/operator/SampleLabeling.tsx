export function SampleLabeling({
  sampleId,
  onClose,
  onChanged,
}: {
  sampleId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  return (
    <div className="p-6">
      sample {sampleId}
      <button type="button" onClick={() => { onChanged(); onClose(); }}>tutup</button>
    </div>
  );
}