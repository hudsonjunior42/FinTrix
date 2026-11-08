//! Armazenamento do FinTrix: documentos JSON identificados por caminho
//! (`data/users/local/livro/l2026/<id>`), num SQLite cifrado com SQLCipher.
//! É o mesmo modelo que a interface usa no navegador (veja `Backends` em index.html).
//!
//! Cada gravação também atualiza a tabela `campos` (uma linha por folha do JSON, com carimbo), que é o
//! que a sincronização troca entre aparelhos (veja `campos` e `sync`).

pub mod campos;
pub mod sync;

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use std::sync::Mutex;

use campos::{achatar, agora_ms, ler_carimbo, remontar, Relogio};

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
    #[error("{0}")]
    Sync(String),
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

/// Um campo como vai para os outros aparelhos: valor None = apagado.
#[derive(Debug, Clone, PartialEq, serde::Serialize, Deserialize)]
pub struct Campo {
    pub path: String,
    pub campo: String,
    pub valor: Option<Value>,
    pub carimbo: String,
}

/// Caminho do documento de configuração e coleções de lançamentos por ano (`.../livro/l2026/<id>`).
pub const CONFIG: &str = "data/users/local/livro";

pub struct Store {
    conn: Mutex<Connection>,
    relogio: Mutex<Relogio>,
    aparelho: String,
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
             );
             -- folhas dos documentos com carimbo (valor NULL = apagado), base da sincronização
             CREATE TABLE IF NOT EXISTS campos (
                 path TEXT NOT NULL,
                 campo TEXT NOT NULL,
                 valor TEXT,
                 carimbo TEXT NOT NULL,
                 PRIMARY KEY (path, campo)
             );
             -- id deste aparelho, configuração da sincronização e o que já foi visto/enviado
             CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);",
        )?;
        let aparelho = match conn.query_row("SELECT valor FROM meta WHERE chave = 'aparelho'", [], |r| r.get::<_, String>(0)) {
            Ok(a) => a,
            Err(rusqlite::Error::QueryReturnedNoRows) => {
                let a = gerar_chave()?[..16].to_string();
                conn.execute("INSERT INTO meta (chave, valor) VALUES ('aparelho', ?1)", params![a])?;
                a
            }
            Err(e) => return Err(e.into()),
        };
        let s = Self { conn: Mutex::new(conn), relogio: Mutex::new(Relogio::default()), aparelho };
        s.semear_campos()?;
        Ok(s)
    }

    /// Id aleatório deste aparelho (aparece nos carimbos e no nome do arquivo de estado).
    pub fn aparelho(&self) -> &str {
        &self.aparelho
    }

    fn novo_carimbo(&self) -> Resultado<String> {
        Ok(self.relogio.lock().map_err(|_| Erro::Bloqueado)?.novo(&self.aparelho))
    }

    /// Bancos de antes da sincronização: cria os campos a partir dos documentos, uma vez.
    fn semear_campos(&self) -> Resultado<()> {
        let tem: i64 = self.com_conn(|c| Ok(c.query_row("SELECT count(*) FROM campos", [], |r| r.get(0))?))?;
        if tem > 0 {
            return Ok(());
        }
        let docs = self.todos()?;
        if docs.is_empty() {
            return Ok(());
        }
        let h = self.novo_carimbo()?;
        let mut conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
        let tx = conn.transaction()?;
        for (p, d) in docs {
            for (campo, v) in achatar(&d) {
                tx.execute("INSERT INTO campos (path, campo, valor, carimbo) VALUES (?1, ?2, ?3, ?4)", params![p, campo, serde_json::to_string(&v)?, h])?;
            }
        }
        tx.commit()?;
        Ok(())
    }

    pub fn meta(&self, chave: &str) -> Resultado<Option<String>> {
        self.com_conn(|c| match c.query_row("SELECT valor FROM meta WHERE chave = ?1", params![chave], |r| r.get(0)) {
            Ok(v) => Ok(Some(v)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.into()),
        })
    }

    /// valor None apaga a chave
    pub fn definir_meta(&self, chave: &str, valor: Option<&str>) -> Resultado<()> {
        self.com_conn(|c| {
            match valor {
                Some(v) => c.execute("INSERT INTO meta (chave, valor) VALUES (?1, ?2) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor", params![chave, v])?,
                None => c.execute("DELETE FROM meta WHERE chave = ?1", params![chave])?,
            };
            Ok(())
        })
    }

    /// Apaga as chaves de meta que começam com o prefixo (ex.: o que foi visto de um cofre).
    pub fn limpar_meta(&self, prefixo: &str) -> Resultado<()> {
        self.com_conn(|c| {
            c.execute("DELETE FROM meta WHERE substr(chave, 1, length(?1)) = ?1", params![prefixo])?;
            Ok(())
        })
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
    /// Os campos que mudaram (e os que sumiram, como apagados) ganham um carimbo novo.
    pub fn lote(&self, ops: &[Op]) -> Resultado<()> {
        let h = self.novo_carimbo()?;
        let mut conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
        let tx = conn.transaction()?;
        for o in ops {
            gravar_campos(&tx, &o.path, o.data.as_ref(), &h)?;
            gravar_doc(&tx, &o.path, o.data.as_ref())?;
        }
        tx.commit()?;
        Ok(())
    }

    /// Todos os campos (inclusive apagados): o estado que este aparelho envia.
    pub fn campos_todos(&self) -> Resultado<Vec<Campo>> {
        self.com_conn(|c| {
            let mut st = c.prepare("SELECT path, campo, valor, carimbo FROM campos ORDER BY path, campo")?;
            let linhas = st.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?, r.get::<_, Option<String>>(2)?, r.get::<_, String>(3)?)))?;
            let mut out = Vec::new();
            for l in linhas {
                let (path, campo, v, carimbo) = l?;
                out.push(Campo { path, campo, valor: v.map(|v| serde_json::from_str(&v)).transpose()?, carimbo });
            }
            Ok(out)
        })
    }

    /// Maior carimbo gravado por ESTE aparelho (para saber se há algo novo a enviar).
    pub fn ultimo_carimbo_local(&self) -> Resultado<Option<String>> {
        let fim = format!("-{}", self.aparelho);
        self.com_conn(|c| {
            Ok(c.query_row("SELECT max(carimbo) FROM campos WHERE substr(carimbo, -length(?1)) = ?1", params![fim], |r| r.get(0))?)
        })
    }

    /// Junta campos vindos de outro aparelho: em cada campo fica o carimbo maior. Carimbos mais de um dia
    /// no futuro são ignorados (relógio errado não pode "ganhar" para sempre).
    /// Devolve os documentos que mudaram aqui, já remontados (None = apagado), para avisar a interface.
    pub fn mesclar(&self, remotos: &[Campo]) -> Resultado<Vec<(String, Option<Value>)>> {
        let limite = agora_ms() + 24 * 3600 * 1000;
        let mut tocados = BTreeSet::new();
        let mut maior = String::new();
        {
            let mut conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
            let tx = conn.transaction()?;
            for r in remotos {
                if !ler_carimbo(&r.carimbo).is_some_and(|(ms, _)| ms <= limite) {
                    continue;
                }
                let local: Option<String> = match tx.query_row("SELECT carimbo FROM campos WHERE path = ?1 AND campo = ?2", params![r.path, r.campo], |x| x.get(0)) {
                    Ok(h) => Some(h),
                    Err(rusqlite::Error::QueryReturnedNoRows) => None,
                    Err(e) => return Err(e.into()),
                };
                if local.as_deref().is_some_and(|l| l >= r.carimbo.as_str()) {
                    continue;
                }
                let v = r.valor.as_ref().map(serde_json::to_string).transpose()?;
                tx.execute(
                    "INSERT INTO campos (path, campo, valor, carimbo) VALUES (?1, ?2, ?3, ?4)
                     ON CONFLICT(path, campo) DO UPDATE SET valor = excluded.valor, carimbo = excluded.carimbo",
                    params![r.path, r.campo, v, r.carimbo],
                )?;
                tocados.insert(r.path.clone());
                if r.carimbo > maior {
                    maior = r.carimbo.clone();
                }
            }
            tx.commit()?;
        }
        if !maior.is_empty() {
            self.relogio.lock().map_err(|_| Erro::Bloqueado)?.observar(&maior);
        }
        let mut mudou = Vec::new();
        {
            let mut conn = self.conn.lock().map_err(|_| Erro::Bloqueado)?;
            let tx = conn.transaction()?;
            for p in &tocados {
                let novo = remontar(&folhas_vivas(&tx, p)?);
                if ler_doc(&tx, p)? != novo {
                    gravar_doc(&tx, p, novo.as_ref())?;
                    mudou.push((p.clone(), novo));
                }
            }
            tx.commit()?;
        }
        mudou.extend(self.conferir_anos()?);
        Ok(mudou)
    }

    /// A interface só carrega os anos listados em `anos` na configuração. Dois aparelhos que criaram anos
    /// diferentes ao mesmo tempo perderiam um deles (a lista vale inteira), então os anos com lançamentos
    /// entram de volta na lista aqui.
    fn conferir_anos(&self) -> Resultado<Vec<(String, Option<Value>)>> {
        let Some(mut cfg) = self.com_conn(|c| ler_doc(c, CONFIG))? else { return Ok(vec![]) };
        let prefixo = format!("{CONFIG}/l");
        let com_dados: BTreeSet<String> = self.com_conn(|c| {
            let mut st = c.prepare("SELECT DISTINCT substr(path, length(?1) + 1, 4) FROM docs WHERE substr(path, 1, length(?1)) = ?1")?;
            let r = st.query_map(params![prefixo], |r| r.get::<_, String>(0))?.collect::<Result<_, _>>()?;
            Ok(r)
        })?;
        let mut anos: BTreeSet<String> = cfg["anos"].as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect()).unwrap_or_default();
        let antes = anos.len();
        anos.extend(com_dados.into_iter().filter(|a| a.len() == 4 && a.chars().all(|c| c.is_ascii_digit())));
        if anos.len() == antes {
            return Ok(vec![]);
        }
        cfg["anos"] = Value::from(anos.into_iter().collect::<Vec<_>>());
        self.gravar(CONFIG, Some(&cfg))?;
        Ok(vec![(CONFIG.to_string(), Some(cfg))])
    }

    /// Para entrar num cofre: tira daqui todos os documentos e campos (os do cofre chegam na mesclagem).
    /// Comprovantes ficam; os do cofre são baixados.
    pub fn esvaziar_documentos(&self) -> Resultado<()> {
        self.com_conn(|c| {
            c.execute_batch("DELETE FROM docs; DELETE FROM campos;")?;
            Ok(())
        })
    }
}

fn ler_doc(c: &Connection, path: &str) -> Resultado<Option<Value>> {
    match c.query_row("SELECT json FROM docs WHERE path = ?1", params![path], |r| r.get::<_, String>(0)) {
        Ok(j) => Ok(Some(serde_json::from_str(&j)?)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

fn gravar_doc(c: &Connection, path: &str, data: Option<&Value>) -> Resultado<()> {
    match data {
        None => c.execute("DELETE FROM docs WHERE path = ?1", params![path])?,
        Some(v) => c.execute(
            "INSERT INTO docs (path, json, atualizado_em) VALUES (?1, ?2, strftime('%s','now'))
             ON CONFLICT(path) DO UPDATE SET json = excluded.json, atualizado_em = excluded.atualizado_em",
            params![path, serde_json::to_string(v)?],
        )?,
    };
    Ok(())
}

fn folhas_vivas(c: &Connection, path: &str) -> Resultado<BTreeMap<String, (Value, String)>> {
    let mut st = c.prepare("SELECT campo, valor, carimbo FROM campos WHERE path = ?1 AND valor IS NOT NULL")?;
    let linhas = st.query_map(params![path], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?, r.get::<_, String>(2)?)))?;
    let mut out = BTreeMap::new();
    for l in linhas {
        let (campo, v, h) = l?;
        out.insert(campo, (serde_json::from_str(&v)?, h));
    }
    Ok(out)
}

/// Unidade de mesclagem de um campo: dentro dela vale a última gravação inteira, e unidades diferentes se
/// juntam. Lançamento = o documento todo. Configuração = cada registro (`contas/<id>`, `cartoes/<id>`,
/// `recorr/<id>`…) ou cada chave simples (`anos`, `versao`). Assim, apagar uma conta num aparelho e editar
/// o nome dela no outro nunca deixa uma conta pela metade (só com o nome).
pub fn unidade<'a>(path: &str, campo: &'a str) -> &'a str {
    if path != CONFIG {
        return "";
    }
    match campo.match_indices('/').nth(1) {
        Some((i, _)) => &campo[..i],
        None => campo,
    }
}

fn na_unidade(u: &str, campo: &str) -> bool {
    u.is_empty() || campo == u || (campo.starts_with(u) && campo.as_bytes().get(u.len()) == Some(&b'/'))
}

/// Compara as folhas novas com as vivas. Toda unidade com alguma diferença é carimbada inteira
/// (folhas que ficaram e que mudaram); folhas que sumiram viram apagadas.
fn gravar_campos(c: &Connection, path: &str, data: Option<&Value>, h: &str) -> Resultado<()> {
    let antes = folhas_vivas(c, path)?;
    let depois = data.map(achatar).unwrap_or_default();
    let mut mudadas: BTreeSet<String> = BTreeSet::new();
    for (campo, v) in &depois {
        if antes.get(campo).map(|(a, _)| a) != Some(v) {
            mudadas.insert(unidade(path, campo).to_string());
        }
    }
    for campo in antes.keys().filter(|k| !depois.contains_key(*k)) {
        mudadas.insert(unidade(path, campo).to_string());
    }
    for (campo, v) in &depois {
        if mudadas.iter().any(|u| na_unidade(u, campo)) {
            c.execute(
                "INSERT INTO campos (path, campo, valor, carimbo) VALUES (?1, ?2, ?3, ?4)
                 ON CONFLICT(path, campo) DO UPDATE SET valor = excluded.valor, carimbo = excluded.carimbo",
                params![path, campo, serde_json::to_string(v)?, h],
            )?;
        }
    }
    for campo in antes.keys().filter(|k| !depois.contains_key(*k)) {
        c.execute("UPDATE campos SET valor = NULL, carimbo = ?3 WHERE path = ?1 AND campo = ?2", params![path, campo, h])?;
    }
    Ok(())
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
