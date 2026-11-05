export async function fetchHealth() {
  const response = await fetch("/api/health");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  const data = await response.json();
  if (data.status !== "ok") throw new Error("예상하지 못한 API 응답입니다.");
  return data;
}
