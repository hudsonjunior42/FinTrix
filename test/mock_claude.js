// banco simulado no formato do db do claude.ai (sem batch/todos), guardado no localStorage para sobreviver a recarregar
(() => {
  const K = "mockdb";
  let M = new Map(JSON.parse(localStorage.getItem(K) || "[]"));
  const save = () => localStorage.setItem(K, JSON.stringify([...M]));
  const pai = p => p.slice(0, p.lastIndexOf("/")), ult = p => p.slice(p.lastIndexOf("/") + 1);
  const subsD = new Map(), subsC = new Map();
  const clone = v => v === undefined ? undefined : JSON.parse(JSON.stringify(v));
  const ehObj = v => v !== null && typeof v === "object" && !Array.isArray(v);
  const merge = (a, b) => { const o = ehObj(a) ? { ...a } : {}; for (const [k, v] of Object.entries(b)) o[k] = ehObj(v) && ehObj(o[k]) ? merge(o[k], v) : v; return o; };
  const snapD = p => ({ id: ult(p), exists: M.has(p), data: () => clone(M.get(p)) });
  const snapC = c => { const docs = [...M.keys()].filter(k => pai(k) === c).sort().map(snapD); return { docs, size: docs.length, empty: !docs.length }; };
  const notify = p => setTimeout(() => { subsD.get(p)?.forEach(f => f(snapD(p))); subsC.get(pai(p))?.forEach(f => f(snapC(pai(p)))); }, 3);
  const wait = () => new Promise(r => setTimeout(r, 0));
  window.__mock = { writes: 0, falharApos: null };
  const escrever = fn => { if (__mock.falharApos != null && __mock.writes >= __mock.falharApos) throw Object.assign(new Error("falha simulada"), { code: "unavailable" }); __mock.writes++; fn(); save(); };
  const sub = (mapa, k, fn, snap) => { let s = mapa.get(k); if (!s) mapa.set(k, s = new Set()); s.add(fn); setTimeout(() => s.has(fn) && fn(snap()), 3); return () => s.delete(fn); };
  function doc(p) {
    return { id: ult(p), path: p,
      get: async () => { await wait(); return snapD(p); },
      set: async d => { await wait(); escrever(() => M.set(p, clone(d))); notify(p); },
      update: async d => { await wait(); if (!M.has(p)) throw Object.assign(new Error("não existe"), { code: "invalid_argument" }); escrever(() => M.set(p, merge(M.get(p), clone(d)))); notify(p); },
      delete: async () => { await wait(); escrever(() => M.delete(p)); notify(p); },
      onSnapshot: fn => sub(subsD, p, fn, () => snapD(p)),
      collection: c => col(p + "/" + c) };
  }
  function col(c) { return { path: c, doc: id => doc(c + "/" + (id || Math.random().toString(36).slice(2))), get: async () => { await wait(); return snapC(c); }, onSnapshot: fn => sub(subsC, c, fn, () => snapC(c)) }; }
  const db = Object.freeze({ doc, collection: col });
  window.__downloads = [];
  window.claude = { use: async n => n === "db" ? db : n === "user" ? { id: async () => "u1" } : n === "downloads" ? { save: async ({ filename, data }) => { __downloads.push({ filename, data }); } } : null };
})();
