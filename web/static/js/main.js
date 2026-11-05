import { fetchHealth } from "./api/client.js";

async function checkApi() {
  const status = document.querySelector("#api-status");
  if (!status) return;

  try {
    const data = await fetchHealth();
    status.textContent = `API 연결: ${data.status}`;
    status.dataset.state = "ok";
  } catch (error) {
    status.textContent = `API 연결 실패: ${error.message}`;
    status.dataset.state = "error";
  }
}

checkApi();
