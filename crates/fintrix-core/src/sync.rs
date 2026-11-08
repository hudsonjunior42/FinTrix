//! Sincronização entre aparelhos por um "cofre" numa pasta (Syncthing, Nextcloud…) ou num bucket S3
//! (Cloudflare R2, Backblaze B2, AWS, MinIO…). Tudo é cifrado aqui antes de sair; o destino só guarda:
//!
//! ```text
//! fintrix/<cofre>/estado/<aparelho>.bin   estado completo (todos os campos) de UM aparelho; só ele grava
//! fintrix/<cofre>/anexos/<código>.bin     um comprovante; código = HMAC do id (não revela nada); imutável
//! ```
//!
//! Cada aparelho lê os estados dos outros, mescla campo a campo (`Store::mesclar`) e regrava o seu.
//! Como cada um só escreve no próprio arquivo, o destino nunca vê duas gravações no mesmo objeto.
//!
//! Arquivo: `FTX1` · formato (1 byte) · tamanho do id do aparelho (1 byte) · id · nonce (24 bytes) ·
//! XChaCha20-Poly1305(deflate(JSON)); tudo antes do texto cifrado entra como dado autenticado.

use std::collections::{BTreeSet, HashSet};
use std::io::{Read, Write};
use std::sync::Arc;

use base64::Engine;
use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{XChaCha20Poly1305, XNonce};
use futures::TryStreamExt;
use hmac::{Hmac, Mac};
use object_store::aws::AmazonS3Builder;
use object_store::local::LocalFileSystem;
use object_store::path::Path as Caminho;
use object_store::ObjectStore;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::Sha256;

use crate::{gerar_chave, Campo, Erro, Resultado, Store, CONFIG};

pub const FORMATO: u8 = 1;
const MAGICO: &[u8; 4] = b"FTX1";
const PREFIXO_CODIGO: &str = "FTX1.";

fn erro<E: std::fmt::Display>(e: E) -> Erro {
    Erro::Sync(e.to_string())
}

/// Erro do bucket/pasta. O `object_store` só mostra "Error performing GET" no nível de cima;
/// a causa de verdade (DNS, TLS, 403…) está nas fontes encadeadas, então juntamos todas
/// e acrescentamos uma dica em português.
fn erro_os(e: object_store::Error) -> Erro {
    use std::error::Error as _;
    let mut texto = e.to_string();
    let mut fonte = e.source();
    while let Some(f) = fonte {
        let t = f.to_string();
        if !texto.contains(&t) {
            texto.push_str(": ");
            texto.push_str(&t);
        }
        fonte = f.source();
    }
    let baixo = texto.to_lowercase();
    let dica = if baixo.contains("dns") || baixo.contains("lookup") || baixo.contains("resolve") {
        "Não foi possível achar o endereço do bucket: confira o endpoint e a conexão com a internet."
    } else if baixo.contains("certificate") || baixo.contains("tls") || baixo.contains("ssl") {
        "Falha de segurança (TLS) ao falar com o bucket: confira o endpoint (use https) e a data/hora do computador."
    } else if baixo.contains("timed out") || baixo.contains("timeout") || baixo.contains("connect") {
        "Não consegui conectar ao bucket: confira o endpoint e a conexão com a internet."
    } else if baixo.contains("403") || baixo.contains("signaturedoesnotmatch") || baixo.contains("invalidaccesskeyid") || baixo.contains("accessdenied") {
        "O bucket recusou as chaves: confira Access key, Secret key e as permissões do bucket."
    } else if baixo.contains("404") || baixo.contains("nosuchbucket") {
        "Bucket não encontrado: confira o nome do bucket, o endpoint e a região."
    } else {
        ""
    };
    if dica.is_empty() { Erro::Sync(texto) } else { Erro::Sync(format!("{dica} ({texto})")) }
}

/// Onde o cofre fica.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "tipo", rename_all = "lowercase")]
pub enum Destino {
    /// Pasta local, normalmente sincronizada por outro programa (Syncthing, Nextcloud, Dropbox).
    Pasta { pasta: String },
    /// Bucket compatível com S3. `endpoint` vazio = AWS; R2: `https://<conta>.r2.cloudflarestorage.com`.
    S3 { endpoint: String, bucket: String, regiao: String, access: String, secret: String },
}

impl Destino {
    /// Para mostrar na tela, sem segredos.
    pub fn descricao(&self) -> String {
        match self {
            Destino::Pasta { pasta } => format!("pasta {pasta}"),
            Destino::S3 { endpoint, bucket, .. } => {
                let host = endpoint.trim_start_matches("https://").trim_start_matches("http://");
                if host.is_empty() { format!("bucket {bucket}") } else { format!("bucket {bucket} em {host}") }
            }
        }
    }
}

/// Um cofre: id (nome da pasta no destino), chave de 256 bits (hex) e destino.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Cofre {
    pub id: String,
    pub chave: String,
    pub destino: Destino,
}

impl Cofre {
    pub fn novo(destino: Destino) -> Resultado<Self> {
        Ok(Cofre { id: gerar_chave()?[..16].to_string(), chave: gerar_chave()?, destino })
    }

    /// Código de pareamento: tudo o que outro aparelho precisa para entrar (inclusive os segredos).
    pub fn codigo(&self) -> Resultado<String> {
        let j = serde_json::to_vec(self)?;
        Ok(format!("{PREFIXO_CODIGO}{}", base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(j)))
    }

    pub fn do_codigo(codigo: &str) -> Resultado<Self> {
        let limpo: String = codigo.chars().filter(|c| !c.is_whitespace()).collect();
        let b64 = limpo.strip_prefix(PREFIXO_CODIGO).ok_or_else(|| erro("Isso não é um código de pareamento do FinTrix."))?;
        let j = base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(b64).map_err(|_| erro("Código de pareamento incompleto ou com erro de digitação."))?;
        let c: Cofre = serde_json::from_slice(&j).map_err(|_| erro("Código de pareamento incompleto ou com erro de digitação."))?;
        if c.chave.len() != 64 || !c.chave.chars().all(|x| x.is_ascii_hexdigit()) {
            return Err(erro("Código de pareamento com chave inválida."));
        }
        Ok(c)
    }

    fn base(&self) -> String {
        format!("fintrix/{}", self.id)
    }
}

/// Subchaves derivadas da chave do cofre (HKDF-SHA256, com o id do cofre como sal).
struct Chaves {
    cifra: [u8; 32],
    nomes: [u8; 32],
}

impl Chaves {
    fn de(cofre: &Cofre) -> Resultado<Self> {
        let bruta: Vec<u8> = (0..32).map(|i| u8::from_str_radix(&cofre.chave[2 * i..2 * i + 2], 16)).collect::<Result<_, _>>().map_err(erro)?;
        let hk = hkdf::Hkdf::<Sha256>::new(Some(cofre.id.as_bytes()), &bruta);
        let (mut cifra, mut nomes) = ([0u8; 32], [0u8; 32]);
        hk.expand(b"fintrix/cifra/v1", &mut cifra).map_err(erro)?;
        hk.expand(b"fintrix/nomes/v1", &mut nomes).map_err(erro)?;
        Ok(Chaves { cifra, nomes })
    }

    fn nome_anexo(&self, id: &str) -> String {
        let mut m = <Hmac<Sha256> as Mac>::new_from_slice(&self.nomes).expect("chave de 32 bytes");
        m.update(id.as_bytes());
        m.finalize().into_bytes()[..16].iter().map(|b| format!("{b:02x}")).collect()
    }
}

fn cifrar(ch: &Chaves, aparelho: &str, dados: &[u8]) -> Resultado<Vec<u8>> {
    let mut nonce = [0u8; 24];
    getrandom::getrandom(&mut nonce).map_err(erro)?;
    let mut cab = Vec::with_capacity(30 + aparelho.len());
    cab.extend_from_slice(MAGICO);
    cab.push(FORMATO);
    cab.push(u8::try_from(aparelho.len()).map_err(erro)?);
    cab.extend_from_slice(aparelho.as_bytes());
    cab.extend_from_slice(&nonce);
    let comprimido = {
        let mut z = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::default());
        z.write_all(dados).map_err(erro)?;
        z.finish().map_err(erro)?
    };
    let ct = XChaCha20Poly1305::new((&ch.cifra).into())
        .encrypt(XNonce::from_slice(&nonce), Payload { msg: &comprimido, aad: &cab })
        .map_err(|_| erro("falha ao cifrar"))?;
    cab.extend_from_slice(&ct);
    Ok(cab)
}

/// (aparelho, dados). Falha se o arquivo foi alterado, é de outro cofre ou de um formato mais novo.
fn decifrar(ch: &Chaves, b: &[u8]) -> Resultado<(String, Vec<u8>)> {
    let invalido = || erro("Arquivo do cofre ilegível: chave diferente ou arquivo alterado.");
    if b.len() < 6 || &b[..4] != MAGICO {
        return Err(invalido());
    }
    if b[4] > FORMATO {
        return Err(erro("O cofre foi gravado por uma versão mais nova do FinTrix. Atualize este aparelho."));
    }
    let n = b[5] as usize;
    let fim_cab = 6 + n + 24;
    if b.len() < fim_cab + 16 {
        return Err(invalido());
    }
    let aparelho = String::from_utf8(b[6..6 + n].to_vec()).map_err(|_| invalido())?;
    let comprimido = XChaCha20Poly1305::new((&ch.cifra).into())
        .decrypt(XNonce::from_slice(&b[6 + n..fim_cab]), Payload { msg: &b[fim_cab..], aad: &b[..fim_cab] })
        .map_err(|_| invalido())?;
    let mut dados = Vec::new();
    flate2::read::DeflateDecoder::new(&comprimido[..]).read_to_end(&mut dados).map_err(|_| invalido())?;
    Ok((aparelho, dados))
}

/// JSON + bytes num corpo só (mesmo formato do `quadro` da casca Tauri).
fn juntar(meta: &Value, bytes: &[u8]) -> Resultado<Vec<u8>> {
    let j = serde_json::to_vec(meta)?;
    let mut out = (j.len() as u32).to_le_bytes().to_vec();
    out.extend_from_slice(&j);
    out.extend_from_slice(bytes);
    Ok(out)
}

fn separar(b: &[u8]) -> Resultado<(Value, &[u8])> {
    let n = b.get(..4).map(|x| u32::from_le_bytes([x[0], x[1], x[2], x[3]]) as usize).ok_or_else(|| erro("anexo curto"))?;
    let meta = b.get(4..4 + n).ok_or_else(|| erro("anexo curto"))?;
    Ok((serde_json::from_slice(meta)?, &b[4 + n..]))
}

/// O que cada aparelho grava no seu arquivo de estado.
#[derive(Debug, Serialize, Deserialize)]
struct Estado {
    formato: u8,
    aparelho: String,
    /// maior versão de dados que o app desse aparelho entende (VERSAO_DADOS do index.html)
    versao_app: u32,
    campos: Vec<Campo>,
}

pub fn conectar(destino: &Destino) -> Resultado<Arc<dyn ObjectStore>> {
    Ok(match destino {
        Destino::Pasta { pasta } => {
            std::fs::create_dir_all(pasta).map_err(|e| erro(format!("Não foi possível usar a pasta {pasta}: {e}")))?;
            Arc::new(LocalFileSystem::new_with_prefix(pasta).map_err(erro)?)
        }
        Destino::S3 { endpoint, bucket, regiao, access, secret } => {
            let mut b = AmazonS3Builder::new()
                .with_bucket_name(bucket)
                .with_region(if regiao.is_empty() { "auto" } else { regiao })
                .with_access_key_id(access)
                .with_secret_access_key(secret);
            let endpoint = endpoint.trim().trim_end_matches('/');
            if !endpoint.is_empty() {
                // o painel do B2 mostra o endpoint sem "https://"
                b = b.with_endpoint(if endpoint.contains("://") { endpoint.to_string() } else { format!("https://{endpoint}") });
            }
            Arc::new(b.build().map_err(erro)?)
        }
    })
}

/// Resultado de um ciclo.
#[derive(Debug, Default, Serialize)]
pub struct Relatorio {
    /// documentos que mudaram aqui (para a interface); None = apagado
    pub alterados: Vec<(String, Option<Value>)>,
    pub outros_aparelhos: usize,
    pub enviou: bool,
    pub anexos_enviados: usize,
    pub anexos_baixados: usize,
}

/// Cofre configurado neste aparelho (guardado no banco cifrado).
pub fn cofre_salvo(store: &Store) -> Resultado<Option<Cofre>> {
    store.meta("sync/cofre")?.map(|j| serde_json::from_str(&j).map_err(Erro::from)).transpose()
}

/// Liga (Some) ou desliga (None) a sincronização. Esquece o que foi visto e enviado do cofre anterior.
pub fn salvar_cofre(store: &Store, cofre: Option<&Cofre>) -> Resultado<()> {
    store.limpar_meta("sync/")?;
    if let Some(c) = cofre {
        store.definir_meta("sync/cofre", Some(&serde_json::to_string(c)?))?;
    }
    Ok(())
}

/// Antes de entrar num cofre (e apagar os dados daqui): o destino responde, tem pelo menos um aparelho
/// e a chave do código abre o arquivo dele. Devolve quantos aparelhos o cofre tem.
pub async fn verificar(cofre: &Cofre) -> Resultado<usize> {
    let os = conectar(&cofre.destino)?;
    let ch = Chaves::de(cofre)?;
    let estados: Vec<_> = os.list(Some(&Caminho::from(format!("{}/estado", cofre.base())))).try_collect().await.map_err(erro_os)?;
    let Some(primeiro) = estados.iter().find(|m| m.location.filename().is_some_and(|n| n.ends_with(".bin"))) else {
        return Err(erro("O cofre está vazio nesse destino. Confira a pasta ou o bucket."));
    };
    let bytes = os.get(&primeiro.location).await.map_err(erro_os)?.bytes().await.map_err(erro_os)?;
    decifrar(&ch, &bytes)?;
    Ok(estados.len())
}

/// Um ciclo: baixa e mescla o estado dos outros aparelhos, envia o deste se mudou, troca comprovantes.
/// `versao_app` é a maior versão de dados que este app entende: estados mais novos não são mesclados.
pub async fn sincronizar(store: &Store, cofre: &Cofre, versao_app: u32) -> Resultado<Relatorio> {
    let os = conectar(&cofre.destino)?;
    let ch = Chaves::de(cofre)?;
    let base = cofre.base();
    let meu = format!("{}.bin", store.aparelho());
    let mut rel = Relatorio::default();

    let estados: Vec<_> = os.list(Some(&Caminho::from(format!("{base}/estado")))).try_collect().await.map_err(erro_os)?;
    let mut tem_o_meu = false;
    for m in estados {
        let Some(nome) = m.location.filename().map(String::from) else { continue };
        if nome == meu {
            tem_o_meu = true;
            continue;
        }
        if !nome.ends_with(".bin") {
            continue;
        }
        rel.outros_aparelhos += 1;
        let marca = m.e_tag.clone().unwrap_or_else(|| format!("{}-{}", m.size, m.last_modified.timestamp_millis()));
        let chave_meta = format!("sync/visto/{nome}");
        if store.meta(&chave_meta)?.as_deref() == Some(marca.as_str()) {
            continue;
        }
        let bytes = os.get(&m.location).await.map_err(erro_os)?.bytes().await.map_err(erro_os)?;
        let (_, dados) = decifrar(&ch, &bytes)?;
        let estado: Estado = serde_json::from_slice(&dados)?;
        let versao_dados = estado.campos.iter().find(|c| c.path == CONFIG && c.campo == "versao").and_then(|c| c.valor.as_ref()?.as_u64());
        if versao_dados.is_some_and(|v| v > versao_app as u64) {
            return Err(erro("Outro aparelho usa uma versão mais nova do FinTrix. Atualize este aparelho para sincronizar."));
        }
        rel.alterados.extend(store.mesclar(&estado.campos)?);
        store.definir_meta(&chave_meta, Some(&marca))?;
    }

    let ultimo = store.ultimo_carimbo_local()?;
    if ultimo.is_some() && (!tem_o_meu || ultimo != store.meta("sync/enviado")?) {
        let estado = Estado { formato: FORMATO, aparelho: store.aparelho().to_string(), versao_app, campos: store.campos_todos()? };
        let arq = cifrar(&ch, store.aparelho(), &serde_json::to_vec(&estado)?)?;
        os.put(&Caminho::from(format!("{base}/estado/{meu}")), arq.into()).await.map_err(erro_os)?;
        store.definir_meta("sync/enviado", ultimo.as_deref())?;
        rel.enviou = true;
    }

    // comprovantes: envia os daqui que faltam lá; baixa os que os lançamentos citam e faltam aqui
    let remotos: HashSet<String> = os
        .list(Some(&Caminho::from(format!("{base}/anexos"))))
        .try_collect::<Vec<_>>()
        .await
        .map_err(erro_os)?
        .into_iter()
        .filter_map(|m| m.location.filename().and_then(|n| n.strip_suffix(".bin")).map(String::from))
        .collect();
    let locais = store.loja_todos("anexos")?;
    let tem_aqui: HashSet<String> = locais.iter().filter_map(|i| i.chave.as_str().map(String::from)).collect();
    for it in &locais {
        let Some(id) = it.chave.as_str() else { continue };
        let nome = ch.nome_anexo(id);
        if remotos.contains(&nome) {
            continue;
        }
        let bytes = store.loja_bytes("anexos", &it.chave)?.unwrap_or_default();
        let arq = cifrar(&ch, store.aparelho(), &juntar(&serde_json::json!({ "id": id, "valor": it.valor }), &bytes)?)?;
        os.put(&Caminho::from(format!("{base}/anexos/{nome}.bin")), arq.into()).await.map_err(erro_os)?;
        rel.anexos_enviados += 1;
    }
    let citados: BTreeSet<String> = store
        .todos()?
        .into_iter()
        .filter(|(p, _)| p.starts_with(&format!("{CONFIG}/l")))
        .flat_map(|(_, d)| d["anexos"].as_array().cloned().unwrap_or_default())
        .filter_map(|a| a["id"].as_str().map(String::from))
        .collect();
    for id in citados.iter().filter(|id| !tem_aqui.contains(*id)) {
        let nome = ch.nome_anexo(id);
        if !remotos.contains(&nome) {
            continue;
        }
        let bytes = os.get(&Caminho::from(format!("{base}/anexos/{nome}.bin"))).await.map_err(erro_os)?.bytes().await.map_err(erro_os)?;
        let (_, dados) = decifrar(&ch, &bytes)?;
        let (meta, arq) = separar(&dados)?;
        store.loja_gravar("anexos", &Value::from(id.as_str()), &meta["valor"], Some(arq))?;
        rel.anexos_baixados += 1;
    }
    store.definir_meta("sync/ultimo", Some(&crate::campos::agora_ms().to_string()))?;
    Ok(rel)
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::{gerar_chave, Op};
    use serde_json::json;

    fn banco(d: &tempfile::TempDir, nome: &str) -> Store {
        Store::abrir(&d.path().join(nome), &gerar_chave().unwrap()).unwrap()
    }

    fn doc(s: &Store, p: &str) -> Option<Value> {
        s.todos().unwrap().into_iter().find(|(x, _)| x == p).map(|(_, v)| v)
    }

    fn lanc(id: &str) -> String {
        format!("{CONFIG}/l2026/{id}")
    }

    #[test]
    fn cifra_e_codigo() {
        let c = Cofre::novo(Destino::Pasta { pasta: "/tmp/x".into() }).unwrap();
        let ch = Chaves::de(&c).unwrap();
        let arq = cifrar(&ch, "ap1", b"segredo segredo segredo").unwrap();
        assert!(!arq.windows(7).any(|w| w == b"segredo"));
        assert_eq!(decifrar(&ch, &arq).unwrap(), ("ap1".to_string(), b"segredo segredo segredo".to_vec()));
        let mut alterado = arq.clone();
        let n = alterado.len() - 1;
        alterado[n] ^= 1;
        assert!(decifrar(&ch, &alterado).is_err());
        let mut outro_ap = arq.clone();
        outro_ap[6] = b'X'; // o cabeçalho é autenticado
        assert!(decifrar(&ch, &outro_ap).is_err());
        let outra = Chaves::de(&Cofre::novo(c.destino.clone()).unwrap()).unwrap();
        assert!(decifrar(&outra, &arq).is_err());
        assert_eq!(Cofre::do_codigo(&format!(" {} \n", c.codigo().unwrap())).unwrap(), c);
        assert!(Cofre::do_codigo("FTX1.abc").is_err());
        assert_ne!(ch.nome_anexo("x1"), ch.nome_anexo("x2"));
    }

    fn pausa() {
        // carimbos em milissegundos diferentes, para "depois" ser depois mesmo
        std::thread::sleep(std::time::Duration::from_millis(3));
    }

    #[test]
    fn mesclar_por_registro() {
        let d = tempfile::tempdir().unwrap();
        let (a, b) = (banco(&d, "a.db"), banco(&d, "b.db"));
        a.gravar(CONFIG, Some(&json!({"versao": 2, "anos": ["2026"], "cartoes": {
            "k1": {"nome": "Roxinho", "limite": 100, "cor": "roxo"}, "k2": {"nome": "Azulzinho", "limite": 200, "cor": "azul"}}}))).unwrap();
        b.mesclar(&a.campos_todos().unwrap()).unwrap();
        assert_eq!(doc(&b, CONFIG), doc(&a, CONFIG));
        // registros diferentes editados ao mesmo tempo: as duas edições ficam
        pausa();
        let mut ca = doc(&a, CONFIG).unwrap();
        ca["cartoes"]["k1"]["limite"] = json!(500);
        a.gravar(CONFIG, Some(&ca)).unwrap();
        let mut cb = doc(&b, CONFIG).unwrap();
        cb["cartoes"]["k2"]["cor"] = json!("verde");
        b.gravar(CONFIG, Some(&cb)).unwrap();
        let (ea, eb) = (a.campos_todos().unwrap(), b.campos_todos().unwrap());
        a.mesclar(&eb).unwrap();
        b.mesclar(&ea).unwrap();
        assert!(a.mesclar(&eb).unwrap().is_empty(), "mesclar de novo não muda nada");
        assert_eq!(doc(&a, CONFIG), doc(&b, CONFIG));
        assert_eq!(doc(&a, CONFIG).unwrap()["cartoes"]["k1"]["limite"], 500);
        assert_eq!(doc(&a, CONFIG).unwrap()["cartoes"]["k2"]["cor"], "verde");
        // o mesmo registro nos dois: vale a última edição inteira, sem misturar
        pausa();
        let mut ca = doc(&a, CONFIG).unwrap();
        ca["cartoes"]["k1"]["cor"] = json!("preto");
        a.gravar(CONFIG, Some(&ca)).unwrap();
        pausa();
        let mut cb = doc(&b, CONFIG).unwrap();
        cb["cartoes"]["k1"]["nome"] = json!("Roxo Gold");
        b.gravar(CONFIG, Some(&cb)).unwrap();
        a.mesclar(&b.campos_todos().unwrap()).unwrap();
        b.mesclar(&a.campos_todos().unwrap()).unwrap();
        assert_eq!(doc(&a, CONFIG).unwrap()["cartoes"]["k1"], json!({"nome": "Roxo Gold", "limite": 500, "cor": "roxo"}));
        assert_eq!(doc(&a, CONFIG), doc(&b, CONFIG));
        // conta apagada num aparelho e editada (depois) no outro: volta inteira, não pela metade
        pausa();
        let mut ca = doc(&a, CONFIG).unwrap();
        ca["cartoes"].as_object_mut().unwrap().remove("k2");
        a.gravar(CONFIG, Some(&ca)).unwrap();
        pausa();
        let mut cb = doc(&b, CONFIG).unwrap();
        cb["cartoes"]["k2"]["limite"] = json!(999);
        b.gravar(CONFIG, Some(&cb)).unwrap();
        a.mesclar(&b.campos_todos().unwrap()).unwrap();
        assert_eq!(doc(&a, CONFIG).unwrap()["cartoes"]["k2"], json!({"nome": "Azulzinho", "limite": 999, "cor": "verde"}));
    }

    #[test]
    fn apagar_editar_e_anos() {
        let d = tempfile::tempdir().unwrap();
        let (a, b) = (banco(&d, "a.db"), banco(&d, "b.db"));
        a.gravar(CONFIG, Some(&json!({"versao": 2, "anos": ["2026"]}))).unwrap();
        a.gravar(&lanc("x1"), Some(&json!({"desc": "Café", "valor": 500}))).unwrap();
        b.mesclar(&a.campos_todos().unwrap()).unwrap();
        // A apaga, depois B edita: a edição é mais nova e o lançamento volta inteiro
        pausa();
        a.gravar(&lanc("x1"), None).unwrap();
        pausa();
        b.gravar(&lanc("x1"), Some(&json!({"desc": "Café", "valor": 700}))).unwrap();
        let mudou = a.mesclar(&b.campos_todos().unwrap()).unwrap();
        assert_eq!(mudou, vec![(lanc("x1"), Some(json!({"desc": "Café", "valor": 700})))]);
        // B apaga por último: some nos dois
        pausa();
        b.gravar(&lanc("x1"), None).unwrap();
        a.mesclar(&b.campos_todos().unwrap()).unwrap();
        assert_eq!(doc(&a, &lanc("x1")), None);
        // anos criados ao mesmo tempo nos dois aparelhos: a lista final tem os dois
        let mut ca = doc(&a, CONFIG).unwrap();
        ca["anos"] = json!(["2026", "2027"]);
        a.lote(&[Op { path: CONFIG.into(), data: Some(ca) }, Op { path: format!("{CONFIG}/l2027/y1"), data: Some(json!({"valor": 1})) }]).unwrap();
        pausa();
        let mut cb = doc(&b, CONFIG).unwrap();
        cb["anos"] = json!(["2026", "2028"]);
        b.lote(&[Op { path: CONFIG.into(), data: Some(cb) }, Op { path: format!("{CONFIG}/l2028/z1"), data: Some(json!({"valor": 2})) }]).unwrap();
        a.mesclar(&b.campos_todos().unwrap()).unwrap();
        assert_eq!(doc(&a, CONFIG).unwrap()["anos"], json!(["2026", "2027", "2028"]));
    }

    #[tokio::test]
    async fn dois_aparelhos_por_uma_pasta() {
        let d = tempfile::tempdir().unwrap();
        let pasta = d.path().join("cofre").display().to_string();
        let (a, b) = (banco(&d, "a.db"), banco(&d, "b.db"));
        a.gravar(CONFIG, Some(&json!({"versao": 2, "anos": ["2026"], "contas": {"c1": {"nome": "Nubank"}}}))).unwrap();
        a.gravar(&lanc("x1"), Some(&json!({"desc": "Mercado", "valor": 25990, "anexos": [{"id": "xa1", "nome": "recibo.pdf"}]}))).unwrap();
        a.loja_gravar("anexos", &json!("xa1"), &json!({"id": "xa1", "nome": "recibo.pdf", "tipo": "application/pdf"}), Some(b"%PDF-1.4 SEGREDO")).unwrap();
        let cofre = Cofre::novo(Destino::Pasta { pasta: pasta.clone() }).unwrap();

        let r = sincronizar(&a, &cofre, 2).await.unwrap();
        assert!(r.enviou);
        assert_eq!(r.anexos_enviados, 1);
        // nada em claro na pasta
        for f in walk(&d.path().join("cofre")) {
            let b = std::fs::read(&f).unwrap();
            for s in [&b"Mercado"[..], b"Nubank", b"SEGREDO", b"recibo"] {
                assert!(!b.windows(s.len()).any(|w| w == s), "{f:?} tem texto em claro");
            }
        }

        // B entra pelo código de pareamento
        let cofre_b = Cofre::do_codigo(&cofre.codigo().unwrap()).unwrap();
        let r = sincronizar(&b, &cofre_b, 2).await.unwrap();
        assert_eq!(r.outros_aparelhos, 1);
        assert_eq!(r.anexos_baixados, 1);
        assert_eq!(doc(&b, &lanc("x1")).unwrap()["valor"], 25990);
        assert_eq!(b.loja_bytes("anexos", &json!("xa1")).unwrap().unwrap(), b"%PDF-1.4 SEGREDO");

        // B edita; A recebe no próximo ciclo e só baixa o que mudou
        b.gravar(&lanc("x1"), Some(&json!({"desc": "Mercado", "valor": 30000, "anexos": [{"id": "xa1", "nome": "recibo.pdf"}]}))).unwrap();
        assert!(sincronizar(&b, &cofre_b, 2).await.unwrap().enviou);
        let r = sincronizar(&a, &cofre, 2).await.unwrap();
        assert_eq!(r.alterados.len(), 1);
        assert_eq!(doc(&a, &lanc("x1")).unwrap()["valor"], 30000);
        let r = sincronizar(&a, &cofre, 2).await.unwrap();
        assert!(r.alterados.is_empty() && !r.enviou);

        // app mais antigo não mescla dados de versão mais nova
        let mut cfg = doc(&b, CONFIG).unwrap();
        cfg["versao"] = json!(3);
        b.gravar(CONFIG, Some(&cfg)).unwrap();
        sincronizar(&b, &cofre_b, 3).await.unwrap();
        assert!(sincronizar(&a, &cofre, 2).await.is_err());
    }

    fn walk(d: &std::path::Path) -> Vec<std::path::PathBuf> {
        let mut out = vec![];
        for e in std::fs::read_dir(d).unwrap() {
            let p = e.unwrap().path();
            if p.is_dir() { out.extend(walk(&p)) } else { out.push(p) }
        }
        out
    }
}
