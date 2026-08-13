const CFG = window.CITADEL_CONFIG;
const sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY);

let currentToken = null;
const $ = (id) => document.getElementById(id);

// ===================== AUTH =====================

async function checkSession() {
  const { data } = await sb.auth.getSession();
  if (data.session) {
    currentToken = data.session.access_token;
    showApp(data.session.user.email);
  } else {
    showLogin();
  }
}

function showLogin() {
  $('loginScreen').classList.remove('hidden');
  $('app').classList.add('hidden');
}

function showApp(email) {
  $('loginScreen').classList.add('hidden');
  $('app').classList.remove('hidden');
  $('userEmail').textContent = email;
}

$('loginBtn').onclick = async () => {
  $('loginError').textContent = '';
  const { error } = await sb.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.href }
  });
  if (error) $('loginError').textContent = error.message;
};

$('logoutBtn').onclick = async () => {
  await sb.auth.signOut();
  currentToken = null;
  showLogin();
};

// ===================== TABS =====================

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`tab-${btn.dataset.tab}`).classList.add('active');
  };
});

// ===================== API HELPER =====================

async function apiCall(path, opts = {}) {
  const base = CFG.API_BASE_URL.replace(/\/$/, '');
  const headers = Object.assign({ 'Authorization': `Bearer ${currentToken}` }, opts.headers || {});
  const resp = await fetch(base + path, Object.assign({}, opts, { headers }));
  let data;
  try {
    data = await resp.json();
  } catch {
    data = { detail: await resp.text() };
  }
  if (!resp.ok) {
    const detail = data.detail;
    const message = (detail && typeof detail === 'object')
      ? (detail.error || JSON.stringify(detail))
      : (detail || `HTTP ${resp.status}`);
    const err = new Error(message);
    err.status = resp.status;
    err.data = data;
    err.detail = detail;
    throw err;
  }
  return data;
}

function renderError(container, err) {
  let extra = '';
  const detail = err.detail;

  if (detail && typeof detail === 'object') {
    if (detail.available_columns) {
      extra += `<div style="margin-top:10px; font-size:12px; color:var(--text-dim);">
        Available columns: ${detail.available_columns.map(escapeHtml).join(', ')}
      </div>`;
    }
    if (detail.did_you_mean) {
      const lines = Object.entries(detail.did_you_mean)
        .map(([need, options]) => `<code>${escapeHtml(need)}</code> → did you mean ${options.map(o => `<code>${escapeHtml(o)}</code>`).join(' or ')}?`)
        .join('<br/>');
      extra += `<div style="margin-top:8px; font-size:12px;">${lines}</div>`;
    }
  }

  container.innerHTML = `<div class="result-error">
    <strong>Request failed${err.status ? ` (HTTP ${err.status})` : ''}</strong><br/>
    ${escapeHtml(err.message)}
    ${extra}
  </div>`;
}

function renderLoading(container, text) {
  container.innerHTML = `<div class="result-loading">${text}</div>`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function statusBadgeClass(status) {
  const s = (status || '').toLowerCase();
  if (s === 'critical' || s === 'high') return 'badge-critical';
  if (s === 'warning' || s === 'medium') return 'badge-warning';
  if (s === 'ok' || s === 'compliant' || s === 'low') return 'badge-ok';
  return 'badge-unknown';
}

function fmtMetric(v) {
  return (v === null || v === undefined) ? '—' : Number(v).toFixed(3);
}

// ===================== SHARED RESULT RENDERING (governance response) =====================

function renderGovernanceResponse(container, data) {
  const biasEntries = Object.entries(data.bias_metrics || {});

  let html = '';

  if (biasEntries.length === 0) {
    html += `<div class="result-loading">No models discovered — nothing to audit yet.</div>`;
  }

  biasEntries.forEach(([modelId, m]) => {
    html += `
      <div class="section-label">${escapeHtml(modelId)}</div>
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Disparate Impact</div>
          <div class="metric-value">${fmtMetric(m.disparate_impact)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Statistical Parity Diff</div>
          <div class="metric-value">${fmtMetric(m.statistical_parity_diff)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Equalized Odds</div>
          <div class="metric-value">${fmtMetric(m.equalized_odds)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Status</div>
          <div class="metric-value"><span class="badge ${statusBadgeClass(m.status)}">${escapeHtml(m.status || 'unknown')}</span></div>
        </div>
      </div>
    `;
  });

  if ((data.alerts || []).length > 0) {
    html += `<div class="section-label">Alerts</div>`;
    data.alerts.forEach(a => {
      html += `<div class="alert-item"><strong>${escapeHtml(a.severity || '')}</strong> — ${escapeHtml(a.message || '')}</div>`;
    });
  }

  if ((data.recommendations || []).length > 0) {
    html += `<div class="section-label">Recommendations</div>`;
    data.recommendations.forEach(r => {
      html += `<div class="rec-item">
        <div class="rec-action">${escapeHtml(r.action || '')}</div>
        <div>${escapeHtml(r.reason || '')}</div>
        <div class="rec-impact">${escapeHtml(r.expected_impact || '')}</div>
      </div>`;
    });
  }

  html += `<details class="raw-json"><summary>Raw response</summary><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></details>`;

  container.innerHTML = html;
}

// ===================== UPLOAD TAB =====================

const dropzone = $('dropzone');
const csvInput = $('csvInput');
const uploadBtn = $('uploadBtn');
let selectedFile = null;

dropzone.onclick = () => csvInput.click();

csvInput.onchange = () => {
  if (csvInput.files[0]) setSelectedFile(csvInput.files[0]);
};

dropzone.ondragover = (e) => { e.preventDefault(); };
dropzone.ondrop = (e) => {
  e.preventDefault();
  if (e.dataTransfer.files[0]) setSelectedFile(e.dataTransfer.files[0]);
};

function setSelectedFile(file) {
  if (!file.name.endsWith('.csv')) {
    $('dropzoneText').textContent = 'That\'s not a .csv file — try again';
    return;
  }
  selectedFile = file;
  $('dropzoneText').textContent = `Selected: ${file.name}`;
  dropzone.classList.add('has-file');
  uploadBtn.disabled = false;
}

uploadBtn.onclick = async () => {
  if (!selectedFile) return;
  const container = $('uploadResult');
  renderLoading(container, 'Uploading and analyzing…');
  uploadBtn.disabled = true;

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const data = await apiCall('/governance/analyze-csv', { method: 'POST', body: formData });
    renderGovernanceResponse(container, data);
  } catch (err) {
    renderError(container, err);
  } finally {
    uploadBtn.disabled = false;
  }
};

// ===================== CONNECT TAB =====================

$('connectBtn').onclick = async () => {
  const container = $('connectResult');
  const accountId = $('accountId').value.trim();
  const roleArn = $('roleArn').value.trim();
  const region = $('region').value.trim();

  if (!accountId || !roleArn) {
    renderError(container, new Error('account_id and iam_role_arn are both required.'));
    return;
  }

  renderLoading(container, 'Assuming role and discovering endpoints — this can take a few seconds…');
  $('connectBtn').disabled = true;

  try {
    const data = await apiCall('/governance/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cloud_provider: 'aws',
        credentials: {
          account_id: accountId,
          iam_role_arn: roleArn,
          region: region || undefined
        }
      })
    });
    renderGovernanceResponse(container, data);
  } catch (err) {
    renderError(container, err);
  } finally {
    $('connectBtn').disabled = false;
  }
};

// ===================== HISTORY TAB =====================

$('statusBtn').onclick = async () => {
  const container = $('historyResult');
  const cloud = $('histCloud').value.trim() || 'aws';
  const modelId = $('histModelId').value.trim();
  const q = modelId
    ? `?cloud_provider=${encodeURIComponent(cloud)}&model_id=${encodeURIComponent(modelId)}`
    : `?cloud_provider=${encodeURIComponent(cloud)}`;

  renderLoading(container, 'Fetching status…');
  try {
    const data = await apiCall(`/governance/status${q}`);
    container.innerHTML = `<pre style="background:#0b0d12;border:1px solid #232734;padding:14px;border-radius:8px;font-size:12px;white-space:pre-wrap;">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  } catch (err) {
    renderError(container, err);
  }
};

$('reportBtn').onclick = async () => {
  const container = $('historyResult');
  const cloud = $('histCloud').value.trim() || 'aws';
  const modelId = $('histModelId').value.trim();
  let q = `?cloud_provider=${encodeURIComponent(cloud)}`;
  if (modelId) q += `&model_id=${encodeURIComponent(modelId)}`;

  renderLoading(container, 'Fetching report…');
  try {
    const data = await apiCall(`/governance/report${q}`);
    container.innerHTML = `<pre style="background:#0b0d12;border:1px solid #232734;padding:14px;border-radius:8px;font-size:12px;white-space:pre-wrap;">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  } catch (err) {
    renderError(container, err);
  }
};

// ===================== INIT =====================

checkSession();