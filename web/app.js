async function postJson(url, body) {
  const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${txt}`);
  }
  return resp.json();
}

function parseList(s) {
  if (!s) return [];
  return s.split(',').map(x => x.trim()).filter(x => x.length);
}

document.getElementById('g_run').addEventListener('click', async () => {
  const body = {
    sex: document.getElementById('g_sex').value,
    age: parseInt(document.getElementById('g_age').value, 10),
    height_cm: parseFloat(document.getElementById('g_height').value),
    weight_kg: parseFloat(document.getElementById('g_weight').value),
    activity: document.getElementById('g_activity').value,
    goal: document.getElementById('g_goal').value,
    weekly_rate_kg: parseFloat(document.getElementById('g_weekly').value),
    dietary_restrictions: parseList(document.getElementById('g_diet').value),
    budget: parseFloat(document.getElementById('g_budget').value)
  };
  const out = document.getElementById('results');
  out.textContent = 'Loading...';
  try {
    const res = await postJson('/calculate_goal', body);
    out.textContent = JSON.stringify(res, null, 2);
  } catch (e) {
    out.textContent = String(e);
  }
});

document.getElementById('n_run').addEventListener('click', async () => {
  const body = {
    calories: parseFloat(document.getElementById('n_cal').value),
    protein_g: parseFloat(document.getElementById('n_pro').value),
    carbs_g: parseFloat(document.getElementById('n_carbs').value),
    fat_g: parseFloat(document.getElementById('n_fat').value),
    dietary_restrictions: parseList(document.getElementById('n_diet').value),
    budget: parseFloat(document.getElementById('n_budget').value)
  };
  const out = document.getElementById('results');
  out.textContent = 'Loading...';
  try {
    const res = await postJson('/calculate_numbers', body);
    out.textContent = JSON.stringify(res, null, 2);
  } catch (e) {
    out.textContent = String(e);
  }
});
