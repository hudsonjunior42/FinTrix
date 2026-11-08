//! Armazenamento do FinTrix: documentos JSON identificados por caminho
//! (`data/users/local/livro/l2026/<id>`), num SQLite cifrado com SQLCipher.
//! É o mesmo modelo que a interface usa no navegador (veja `Backends` em index.html).

use std::path::Path;
use std::sync::Mutex;

use rusqlite::{params, Connection};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, thiserror::Error)]
pub enum Erro {
    #[error("banco de dados: {0}")]
    Banco(#[from] rusqlite::Error),
    #[error("JSON inválido: {0}")]
    Json(#[from] serde_json::Error),
    #[error("chave incorreta ou arquivo que não é um banco do FinTrix")]
    ChaveIncorreta,
    #[error("não foi possível gerar a chave: {0}")]
    Aleatorio(String),
    #[error("estado interno bloqueado")]
    Bloqueado,
}

pub type Resultado<T> = Result<T, Erro>;

/// Uma gravação: `data = None` apaga o documento.
#[derive(Debug, Clone, Deserialize)]
pub struct Op {
    pub path: String,
    pub data: Option<Value>,
}

/// Um item de loja; `bytes` é o tamanho do arquivo guardado junto, se houver.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct Item {
    pub chave: Value,
    pub valor: Value,
    pub bytes: Option<i64>,
}

pub struct Store {
    conn: Mutex<Connection>,
}

/// Gera uma chave aleatória de 256 bits em hexadecimal (64 caracteres).
pub fn gerar_chave() -> Resultado<String> {
    let mut b = [0u8; 32];
    getrandom::getrandom(&mut b).map_err(|e| Erro::Aleatorio(e.to_string()))?;
    Ok(b.iter().map(|x| format!("{x:02x}")).collect())
}

impl Store {
    /// Abre (ou cria) o banco cifrado. `chave_hex` são 64 caracteres hexadecimais.
    pub fn abrir(caminho: &Path, chave_hex: &str) -> Resultado<Self> {
        let conn = Connection::open(caminho)?;
        // chave bruta: o SQLCipher não passa por derivação de senha
        conn.pragma_update(None, "key", format!("x'{chave_hex}'"))?;
        // com chave errada a primeira leitura falha; é aqui que detectamos
        conn.query_row("SELECT count(*) FROM sqlite_master", [], |r| r.get::<_, i64>(0))
            .map_err(|_| Erro::ChaveIncorreta)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA secure_delete = ON;
             CREATE TABLE IF NOT EXISTS docs (
                 path TEXT PRIMARY KEY,
                 json TEXT NOT NULL,
                 atualizado_em INTEGER NOT NULL DEFAULT (strftime('%s','now'))
             );
             -- o que no navegador fica em outros IndexedDB: cópias automáticas, preferências do sistema e comprovantes.
             -- chave = JSON da chave (5 ou \"x1a2b\"); bytes = conteúdo do arquivo, quando houver
             CREATE TABLE IF NOT EXISTS itens (
                 loja TEXT NOT NULL,
                 chave TEXT NOT NULL,
                 valor TEXT NOT NULL,
                 bytes BLOB,
                 PRIMARY KEY (loja, chave)
             );",
        )?;
        Ok(Self { conn: Mutex::new(conn) })
    }

    fn com_conn<T>(&self, f: impl FnOnce(&Connection) -> Resultado<T>) -> Resultado<T> {
        let conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
        f(&conn)
    }

    /// Itens de uma loja, sem o conteúdo dos arquivos (só o tamanho em `bytes`).
    pub fn loja_todos(&self, loja: &str) -> Resultado<Vec<Item>> {
        self.com_conn(|c| {
            let mut st = c.prepare("SELECT chave, valor, length(bytes) FROM itens WHERE loja = ?1 ORDER BY chave")?;
            let linhas = st.query_map(params![loja], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?, r.get::<_, Option<i64>>(2)?)))?;
            let mut out = Vec::new();
            for l in linhas {
                let (k, v, b) = l?;
                out.push(Item { chave: serde_json::from_str(&k)?, valor: serde_json::from_str(&v)?, bytes: b });
            }
            Ok(out)
        })
    }

    pub fn loja_get(&self, loja: &str, chave: &Value) -> Resultado<Option<Item>> {
        let k = serde_json::to_string(chave)?;
        self.com_conn(|c| {
            let r = c.query_row(
                "SELECT valor, length(bytes) FROM itens WHERE loja = ?1 AND chave = ?2",
                params![loja, k],
                |r| Ok((r.get::<_, String>(0)?, r.get::<_, Option<i64>>(1)?)),
            );
            match r {
                Ok((v, b)) => Ok(Some(Item { chave: chave.clone(), valor: serde_json::from_str(&v)?, bytes: b })),
                Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
                Err(e) => Err(e.into()),
            }
        })
    }

    pub fn loja_bytes(&self, loja: &str, chave: &Value) -> Resultado<Option<Vec<u8>>> {
        let k = serde_json::to_string(chave)?;
        self.com_conn(|c| {
            match c.query_row("SELECT bytes FROM itens WHERE loja = ?1 AND chave = ?2", params![loja, k], |r| r.get::<_, Option<Vec<u8>>>(0)) {
                Ok(b) => Ok(b),
                Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
                Err(e) => Err(e.into()),
            }
        })
    }

    pub fn loja_gravar(&self, loja: &str, chave: &Value, valor: &Value, bytes: Option<&[u8]>) -> Resultado<()> {
        let (k, v) = (serde_json::to_string(chave)?, serde_json::to_string(valor)?);
        self.com_conn(|c| {
            c.execute(
                "INSERT INTO itens (loja, chave, valor, bytes) VALUES (?1, ?2, ?3, ?4)
                 ON CONFLICT(loja, chave) DO UPDATE SET valor = excluded.valor, bytes = excluded.bytes",
                params![loja, k, v, bytes],
            )?;
            Ok(())
        })
    }

    /// Como o `add` de um object store com `autoIncrement`: o id é o maior id numérico + 1 e vai também em `valor.id`.
    pub fn loja_adicionar(&self, loja: &str, valor: &Value) -> Resultado<i64> {
        let mut conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
        let tx = conn.transaction()?;
        let id: i64 = tx.query_row(
            "SELECT coalesce(max(CAST(chave AS INTEGER)), 0) + 1 FROM itens WHERE loja = ?1 AND chave GLOB '[0-9]*'",
            params![loja],
            |r| r.get(0),
        )?;
        let mut v = valor.clone();
        if let Value::Object(m) = &mut v {
            m.insert("id".into(), Value::from(id));
        }
        tx.execute(
            "INSERT INTO itens (loja, chave, valor) VALUES (?1, ?2, ?3)",
            params![loja, id.to_string(), serde_json::to_string(&v)?],
        )?;
        tx.commit()?;
        Ok(id)
    }

    pub fn loja_apagar(&self, loja: &str, chave: &Value) -> Resultado<()> {
        let k = serde_json::to_string(chave)?;
        self.com_conn(|c| {
            c.execute("DELETE FROM itens WHERE loja = ?1 AND chave = ?2", params![loja, k])?;
            Ok(())
        })
    }

    pub fn loja_limpar(&self, loja: &str) -> Resultado<()> {
        self.com_conn(|c| {
            c.execute("DELETE FROM itens WHERE loja = ?1", params![loja])?;
            Ok(())
        })
    }

    /// Todos os documentos, como `[caminho, dados]`.
    pub fn todos(&self) -> Resultado<Vec<(String, Value)>> {
        let conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
        let mut st = conn.prepare("SELECT path, json FROM docs ORDER BY path")?;
        let linhas = st.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))?;
        let mut out = Vec::new();
        for l in linhas {
            let (p, j) = l?;
            out.push((p, serde_json::from_str(&j)?));
        }
        Ok(out)
    }

    pub fn gravar(&self, path: &str, data: Option<&Value>) -> Resultado<()> {
        self.lote(&[Op { path: path.to_string(), data: data.cloned() }])
    }

    /// Várias gravações numa transação só: ou grava tudo, ou nada.
    pub fn lote(&self, ops: &[Op]) -> Resultado<()> {
        let mut conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
        let tx = conn.transaction()?;
        for o in ops {
            match &o.data {
                None => {
                    tx.execute("DELETE FROM docs WHERE path = ?1", params![o.path])?;
                }
                Some(v) => {
                    tx.execute(
                        "INSERT INTO docs (path, json, atualizado_em) VALUES (?1, ?2, strftime('%s','now'))
                         ON CONFLICT(path) DO UPDATE SET json = excluded.json, atualizado_em = excluded.atualizado_em",
                        params![o.path, serde_json::to_string(v)?],
                    )?;
                }
            }
        }
        tx.commit()?;
        Ok(())
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use serde_json::json;

    fn novo() -> (tempfile::TempDir, std::path::PathBuf, String) {
        let d = tempfile::tempdir().unwrap();
        let p = d.path().join("fintrix.db");
        (d, p, gerar_chave().unwrap())
    }

    #[test]
    fn grava_le_e_apaga() {
        let (_d, p, k) = novo();
        let s = Store::abrir(&p, &k).unwrap();
        s.gravar("a/b", Some(&json!({"valor": 2590, "desc": "Café"}))).unwrap();
        assert_eq!(s.todos().unwrap(), vec![("a/b".to_string(), json!({"valor": 2590, "desc": "Café"}))]);
        s.gravar("a/b", Some(&json!({"valor": 100}))).unwrap();
        assert_eq!(s.todos().unwrap()[0].1, json!({"valor": 100}));
        s.gravar("a/b", None).unwrap();
        assert!(s.todos().unwrap().is_empty());
    }

    #[test]
    fn lote_e_atomico() {
        let (_d, p, k) = novo();
        let s = Store::abrir(&p, &k).unwrap();
        s.lote(&[
            Op { path: "x/1".into(), data: Some(json!(1)) },
            Op { path: "x/2".into(), data: Some(json!(2)) },
        ])
        .unwrap();
        s.lote(&[
            Op { path: "x/1".into(), data: None },
            Op { path: "x/3".into(), data: Some(json!(3)) },
        ])
        .unwrap();
        let ids: Vec<_> = s.todos().unwrap().into_iter().map(|(p, _)| p).collect();
        assert_eq!(ids, ["x/2", "x/3"]);
    }

    #[test]
    fn persiste_ao_reabrir() {
        let (_d, p, k) = novo();
        Store::abrir(&p, &k).unwrap().gravar("c", Some(&json!({"ok": true}))).unwrap();
        assert_eq!(Store::abrir(&p, &k).unwrap().todos().unwrap().len(), 1);
    }

    #[test]
    fn chave_errada_e_recusada() {
        let (_d, p, k) = novo();
        Store::abrir(&p, &k).unwrap().gravar("c", Some(&json!(1))).unwrap();
        let outra = gerar_chave().unwrap();
        assert!(matches!(Store::abrir(&p, &outra), Err(Erro::ChaveIncorreta)));
    }

    #[test]
    fn lojas_com_autoincremento_e_bytes() {
        let (_d, p, k) = novo();
        let s = Store::abrir(&p, &k).unwrap();
        assert_eq!(s.loja_adicionar("copias", &json!({"motivo": "a"})).unwrap(), 1);
        assert_eq!(s.loja_adicionar("copias", &json!({"motivo": "b"})).unwrap(), 2);
        assert_eq!(s.loja_get("copias", &json!(2)).unwrap().unwrap().valor, json!({"motivo": "b", "id": 2}));
        s.loja_apagar("copias", &json!(1)).unwrap();
        assert_eq!(s.loja_todos("copias").unwrap().len(), 1);

        s.loja_gravar("anexos", &json!("x1"), &json!({"id": "x1", "tipo": "application/pdf"}), Some(b"%PDF-1.4")).unwrap();
        let it = s.loja_get("anexos", &json!("x1")).unwrap().unwrap();
        assert_eq!(it.bytes, Some(8));
        assert_eq!(s.loja_bytes("anexos", &json!("x1")).unwrap().unwrap(), b"%PDF-1.4");
        assert!(s.loja_get("anexos", &json!("x2")).unwrap().is_none());
        s.loja_limpar("anexos").unwrap();
        assert!(s.loja_todos("anexos").unwrap().is_empty());
        // limpar uma loja não mexe nas outras
        assert_eq!(s.loja_todos("copias").unwrap().len(), 1);
    }

    #[test]
    fn arquivo_nao_e_sqlite_legivel() {
        let (_d, p, k) = novo();
        Store::abrir(&p, &k).unwrap().gravar("c", Some(&json!({"segredo": "salario-12345"}))).unwrap();
        let bytes = std::fs::read(&p).unwrap();
        assert!(!bytes.starts_with(b"SQLite format 3"));
        assert!(!bytes.windows(13).any(|w| w == b"salario-12345"));
    }
}
