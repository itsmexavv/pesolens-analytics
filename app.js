/* No external scripts. All user-controlled text is escaped before rendering. */
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const peso = cents => new Intl.NumberFormat('en-PH', {style:'currency', currency:'PHP'}).format(cents/100);
const today = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
const option = (value, name) => `<option value="${esc(value)}">${esc(name)}</option>`;
const field = (label, name, type='text', extra='') => `<label class="field">${label}<input name="${name}" type="${type}" ${extra} required></label>`;
const stat = (label, value) => `<div class="stat"><span>${label}</span><strong>${esc(value)}</strong></div>`;
const empty = cols => `<tr><td class="empty" colspan="${cols}">No records yet. Add one to get started.</td></tr>`;
let toastTimer;
function toast(message, error=false) { const el=$('#toast'); el.textContent=message; el.className=error?'error':''; el.hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.hidden=true,6000); }
async function api(app, path, method='GET', data) {
  const response = await fetch(`/api/${app}${path}`, {method, ...(data===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}
function bindForm(selector, action) {
  $(selector).addEventListener('submit', async event => {
    event.preventDefault(); const form=event.currentTarget, button=form.querySelector('button[type="submit"]');
    button.disabled=true;
    try { await action(Object.fromEntries(new FormData(form)), form); } catch(error) { toast(error.message,true); }
    finally { button.disabled=false; }
  });
}
function bindAction(selector, action) {
  $(selector).addEventListener('click', async event => { const button=event.target.closest('button'); if(!button) return; button.disabled=true;
    try { await action(button); } catch(error) { toast(error.message,true); } finally { button.disabled=false; }
  });
}
function hero(number, heading, description, track) { return `<header class="hero hero-row"><div><div class="eyebrow">PesoLens / ${track}</div><h1>${heading}</h1><p>${description}</p></div><span class="badge">Interactive demo</span></header>`; }
async function pesoLens() {
  $('#view').innerHTML=hero('03','See where your pesos go.','Explore monthly income and expenses, compare spending categories and import your own CSV records.','Data & analytics')+`<div class="toolbar"><label class="field">Reporting month<input type="month" id="month" required></label><a id="export" class="button secondary">Export month CSV</a></div><div class="stats" id="stats"></div><div class="split"><div><section class="panel"><h2>Spending by category</h2><div id="categories" class="bars"></div></section><section class="panel"><h2>Transaction history</h2><div class="table-wrap"><table><thead><tr><th>Details</th><th>Date</th><th>Amount</th><th>Action</th></tr></thead><tbody id="transactions"></tbody></table></div></section></div><div><section class="panel"><h2>Add transaction</h2><form id="transaction-form"><label class="field">Type<select name="kind">${option('expense','Expense')}${option('income','Income')}</select></label>${field('Category','category','text','maxlength="50"')}${field('Amount (PHP)','amount','number','min="0.01" max="1000000" step="0.01"')}${field('Date','date','date')}<label class="field">Note (optional)<input name="note" maxlength="300"></label><button type="submit">Add transaction</button></form></section><section class="panel"><h2>Import a CSV</h2><p>Columns: kind, category, amount, date, note. All rows are validated before any are saved.</p><form id="import-form"><label class="field">CSV file<input type="file" name="file" accept=".csv,text/csv" required></label><button type="submit" class="secondary">Import transactions</button></form><p class="hint">Imports append rows. Importing the same file again creates duplicates.</p></section></div></div>`;
  $('#month').value=today().slice(0,7); $('#transaction-form [name="date"]').value=today();
  async function refresh() { const month=$('#month').value; if(!month) return; const [summary,list]=await Promise.all([api('peso',`/summary?month=${month}`),api('peso',`/transactions?month=${month}`)]); $('#stats').innerHTML=stat('Income',peso(summary.income))+stat('Expenses',peso(summary.expense))+stat('Balance',peso(summary.balance)); $('#export').href=`/api/peso/export?month=${month}`; $('#export').download=`expenses-${month}.csv`; $('#categories').innerHTML=summary.categories.map(c=>`<div><div class="bar-label"><span>${esc(c.category)}</span><span>${peso(c.total)} · ${Math.round(c.total/summary.expense*100)}%</span></div><svg class="bar-svg" viewBox="0 0 100 9" preserveAspectRatio="none" aria-hidden="true"><rect width="100" height="9" rx="4" fill="#eef2e5"/><rect width="${c.total/summary.expense*100}" height="9" rx="4" fill="#587b48"/></svg></div>`).join('')||'<p class="empty">No expenses in this month.</p>'; $('#transactions').innerHTML=list.map(r=>`<tr><td><strong>${esc(r.category)}</strong><small>${esc(r.note)} · ${r.kind}</small></td><td>${r.transaction_date}</td><td>${r.kind==='expense'?'−':'+'}${peso(r.amount_cents)}</td><td><button class="small danger" data-id="${r.id}" aria-label="Delete ${esc(r.category)} transaction">Delete</button></td></tr>`).join('')||empty(4); }
  $('#month').addEventListener('change',()=>refresh().catch(e=>toast(e.message,true)));
  bindForm('#transaction-form',async(d,f)=>{ await api('peso','/transactions','POST',d); $('#month').value=d.date.slice(0,7); f.reset(); f.elements.date.value=today(); await refresh(); toast('Transaction added.'); });
  bindAction('#transactions',async b=>{ if(!confirm('Delete this transaction?')) return; await api('peso',`/transactions/${b.dataset.id}`,'DELETE',{}); await refresh(); toast('Transaction deleted.'); });
  bindForm('#import-form',async(d,f)=>{ const file=f.elements.file.files[0]; if(file.size>100000) throw new Error('Choose a CSV smaller than 100 KB.'); const result=await api('peso','/import','POST',{csv:await file.text()}); await refresh(); toast(`${result.imported} transactions imported. Select their month to view them.`); f.reset(); });
  await refresh();
}
Promise.resolve().then(()=>pesoLens()).catch(error=>{toast(error.message,true); console.error(error);});
