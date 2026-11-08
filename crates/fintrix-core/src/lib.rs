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
             );",
        )?;
        Ok(Self { conn: Mutex::new(conn) })
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
    fn arquivo_nao_e_sqlite_legivel() {
        let (_d, p, k) = novo();
        Store::abrir(&p, &k).unwrap().gravar("c", Some(&json!({"segredo": "salario-12345"}))).unwrap();
        let bytes = std::fs::read(&p).unwrap();
        assert!(!bytes.starts_with(b"SQLite format 3"));
        assert!(!bytes.windows(13).any(|w| w == b"salario-12345"));
    }
}
