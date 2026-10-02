// Shared by the validator results page and the project page.
// Backend re-validates on every call; this only transports the request.
window.prismPublish = async function (projectPath, identity) {
  const resp = await fetch('/api/projects/datalad-server/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_path: projectPath, ...(identity || {}) }),
  });
  const body = await resp.json();
  body.http_status = resp.status;
  return body;
};
