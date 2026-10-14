// Banco em memória que imita a API do capability `db` (só para teste local).
(() => {
  const store = new Map();
  const docL = new Map();   // path -> Set(cb)
  const colL = new Map();   // colPath -> Set(cb)
  const clone = o => JSON.parse(JSON.stringify(o));
  const freeze = o => { if (o && typeof o === "object") { Object.values(o).forEach(freeze); Object.freeze(o); } return o; };
  const parent = p => p.split("/").slice(0, -1).join("/");
  const isObj = v => v && typeof v === "object" && !Array.isArray(v);
  function merge(a, b) { const out = { ...a }; for (const [k, v] of Object.entries(b)) out[k] = isObj(v) && isObj(out[k]) ? merge(out[k], v) : clone(v); return out; }
  function snapDoc(path) { const d = store.get(path); return { id: path.split("/").pop(), exists: !!d, data: () => (d ? freeze(clone(d)) : undefined), metadata: { fromCache: false, hasPendingWrites: false } }; }
  function snapCol(path) { const docs = [...store.keys()].filter(k => parent(k) === path).sort().map(snapDoc); return { docs, size: docs.length, empty: !docs.length, docChanges: () => [], metadata: { fromCache: false, hasPendingWrites: false } }; }
  function notify(path) { setTimeout(() => { (docL.get(path) || []).forEach(cb => cb(snapDoc(path))); (colL.get(parent(path)) || []).forEach(cb => cb(snapCol(parent(path)))); }, 0); }
  window.__store = store;
  window.__writes = 0;
  const lat = () => new Promise(r => setTimeout(r, 2));
  function docRef(path) {
    if (path.split("/").length % 2) throw new TypeError("doc path parity " + path);
    return {
      id: path.split("/").pop(), path,
      async get() { await lat(); return snapDoc(path); },
      async set(data) { await lat(); window.__writes++; store.set(path, clone(data)); notify(path); },
      async update(data) { await lat(); if (!store.has(path)) throw { code: "invalid_argument", message: "missing" }; window.__writes++; store.set(path, merge(store.get(path), data)); notify(path); },
      async delete() { await lat(); window.__writes++; store.delete(path); notify(path); },
      onSnapshot(cb, err) { if (!docL.has(path)) docL.set(path, new Set()); docL.get(path).add(cb); setTimeout(() => cb(snapDoc(path)), 0); return () => docL.get(path).delete(cb); },
      collection(sub) { return colRef(path + "/" + sub); },
    };
  }
  function colRef(path) {
    if (!(path.split("/").length % 2)) throw new TypeError("collection path parity " + path);
    return {
      path,
      doc(id) { return docRef(path + "/" + (id || Math.random().toString(36).slice(2))); },
      async add(d) { const r = this.doc(); await r.set(d); return r; },
      async get() { await lat(); return snapCol(path); },
      onSnapshot(cb) { if (!colL.has(path)) colL.set(path, new Set()); colL.get(path).add(cb); setTimeout(() => cb(snapCol(path)), 0); return () => colL.get(path).delete(cb); },
      where() { return this; }, orderBy() { return this; }, limit() { return this; },
    };
  }
  const db = Object.freeze({ doc: docRef, collection: colRef });
  const user = Object.freeze({ id: async () => "u_teste", isOwner: async () => true, canEdit: async () => true, can: async () => true, me: async () => ({ id: "u_teste", name: "", isOwner: true }) });
  const downloads = Object.freeze({ save: async r => { window.__download = { filename: r.filename, size: String(r.data).length, head: String(r.data).slice(0, 400) }; return { status: "saved" }; } });
  window.claude = { use: name => new Promise(res => setTimeout(() => res({ db, user, downloads }[name] || null), 5)) };
})();
