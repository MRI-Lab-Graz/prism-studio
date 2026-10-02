// Shared by the validator results page and the project page.
// Backend re-validates on every call; this only transports the request.
window.prismPublish = async function (projectPath, identity) {
  const resp = await fetch('/api/projects/datalad-server/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_path: projectPath, ...(identity || {}) }),
  });
  let body;
  try {
    body = await resp.json();
  } catch (e) {
    return {
      success: false, reason: 'bad_response', errors: [], http_status: resp.status,
      message: 'Server returned an unexpected response (HTTP ' + resp.status + ').',
    };
  }
  body.http_status = resp.status;
  return body;
};
