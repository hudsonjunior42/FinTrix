//! A casca do FinTrix: desktop (main.rs chama `run`) e Android (`mobile_entry_point`).
//! O que só existe num deles fica atrás de `#[cfg(desktop)]` / `#[cfg(mobile)]`.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, RwLock};

use fintrix_core::sync::{self, Cofre, Destino};
use fintrix_core::{gerar_chave, Erro, Item, Op, Store};
use serde_json::{json, Value};
use tauri::ipc::{InvokeBody, Request, Response};
use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

/// Igual ao `identifier` do tauri.conf.json: nome do serviço no chaveiro e da pasta de dados.
#[cfg(desktop)]
const SERVICO: &str = "io.github.hudsonjunior42.fintrix";
/// Identificador das primeiras versões do protótipo; os dados de lá são trazidos uma vez.
#[cfg(desktop)]
const ANTIGO: &str = "br.com.fintrix.app";
#[cfg(desktop)]
const USUARIO: &str = "chave-do-banco";

/// O banco aberto e a chave dele. Fica vazio (trancado) quando a chave não está no chaveiro:
/// a interface pede a chave de recuperação (`informar_chave`).
struct Banco {
    arquivo: PathBuf,
    aberto: RwLock<Option<(Arc<Store>, String)>>,
    motivo: RwLock<Option<&'static str>>,
}

impl Banco {
    fn store(&self) -> Result<Arc<Store>, String> {
        let g = self.aberto.read().map_err(|_| "estado bloqueado")?;
        g.as_ref().map(|(s, _)| s.clone()).ok_or_else(|| "banco trancado: informe a chave".into())
    }
}

/// Estado da sincronização em segundo plano. `versao` é o VERSAO_DADOS do app (vem da interface).
#[derive(Default)]
struct Sincronia {
    versao: std::sync::Mutex<Option<u32>>,
    rodando: tokio::sync::Mutex<()>,
    erro: std::sync::Mutex<Option<String>>,
    outros: std::sync::Mutex<usize>,
    acordar: tokio::sync::Notify,
}

fn texto<E: std::fmt::Display>(e: E) -> String {
    e.to_string()
}

/// Chave guardada no chaveiro. Ok(None) = não há chave; Err = chaveiro indisponível.
fn ler_chave() -> Result<Option<String>, String> {
    // testes (só em debug): a chave vem do ambiente, sem tocar no chaveiro real; vazia = sem chave
    #[cfg(debug_assertions)]
    if let Ok(k) = std::env::var("FINTRIX_CHAVE") {
        return Ok(Some(k).filter(|k| !k.is_empty()));
    }
    chaveiro::ler()
}

fn guardar_chave(k: &str) -> Result<(), String> {
    #[cfg(debug_assertions)]
    if std::env::var_os("FINTRIX_CHAVE").is_some() {
        return Ok(());
    }
    chaveiro::guardar(k)
}

/// Chaveiro do sistema (Secret Service no Linux, Keychain, Credential Manager).
#[cfg(desktop)]
mod chaveiro {
    use super::{texto, SERVICO, USUARIO};

    pub fn ler() -> Result<Option<String>, String> {
        match keyring::Entry::new(SERVICO, USUARIO).map_err(texto)?.get_password() {
            Ok(k) => Ok(Some(k)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(format!("chaveiro do sistema indisponível: {e}")),
        }
    }

    pub fn guardar(k: &str) -> Result<(), String> {
        keyring::Entry::new(SERVICO, USUARIO).map_err(texto)?.set_password(k).map_err(texto)
    }
}

/// Celular: a chave vai para o Android Keystore (etapa 3 de docs/android.md). Até lá, o build de debug
/// usa uma chave fixa de teste (só com dados de teste) e o de release não abre o banco: a interface pede a chave.
#[cfg(mobile)]
mod chaveiro {
    #[cfg(debug_assertions)]
    const TESTE: &str = "746573746500000000000000000000000000000000000000000000000000f1a0";

    pub fn ler() -> Result<Option<String>, String> {
        #[cfg(debug_assertions)]
        return Ok(Some(TESTE.into()));
        #[cfg(not(debug_assertions))]
        Err("o chaveiro do celular ainda não está disponível".into())
    }

    pub fn guardar(_k: &str) -> Result<(), String> {
        #[cfg(debug_assertions)]
        return Ok(());
        #[cfg(not(debug_assertions))]
        Err("o chaveiro do celular ainda não está disponível".into())
    }
}

fn pasta_de_dados(app: &AppHandle) -> tauri::Result<PathBuf> {
    #[cfg(debug_assertions)]
    if let Some(d) = std::env::var_os("FINTRIX_DADOS") {
        return Ok(PathBuf::from(d));
    }
    app.path().app_data_dir()
}

/// Traz o banco e a chave do identificador antigo, se a pasta nova ainda não tem banco.
/// O resto da pasta antiga (dados da WebView) fica onde está e pode ser apagado.
#[cfg(desktop)]
fn migrar_do_antigo(app: &AppHandle, dir: &Path) {
    if dir.join("fintrix.db").exists() || std::env::var_os("FINTRIX_DADOS").is_some() {
        return;
    }
    let Ok(antigo) = app.path().data_dir().map(|d| d.join(ANTIGO)) else { return };
    if !antigo.join("fintrix.db").exists() {
        return;
    }
    if let Ok(e) = keyring::Entry::new(ANTIGO, USUARIO) {
        if let Ok(k) = e.get_password() {
            if guardar_chave(&k).is_err() {
                return; // sem a chave no lugar novo, não move nada
            }
            let _ = e.delete_credential();
        }
    }
    for nome in ["fintrix.db", "fintrix.db-wal", "fintrix.db-shm"] {
        let de = antigo.join(nome);
        if de.exists() {
            let _ = fs::rename(&de, dir.join(nome));
        }
    }
}

/// Pasta só do usuário (700): o banco é cifrado, mas a WebView guarda preferências em claro ali dentro.
fn restringir(dir: &Path) {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(dir, fs::Permissions::from_mode(0o700));
    }
}

/// Ícone da janela e atalho no menu para quem roda o AppImage ou o executável solto. No Wayland (KDE, GNOME)
/// o ícone vem do arquivo .desktop e do ícone com o mesmo nome do app_id (o identificador, via `set_prgname`);
/// sem eles a janela fica com o ícone genérico. O .deb instala os seus; aqui só grava ou atualiza o que falta.
#[cfg(target_os = "linux")]
fn registrar_atalho(app: &AppHandle) {
    let icone_sistema = Path::new("/usr/share/icons/hicolor/256x256/apps").join(format!("{SERVICO}.png"));
    if cfg!(debug_assertions) || std::env::var_os("FINTRIX_DADOS").is_some() || icone_sistema.exists() {
        return;
    }
    let Ok(base) = app.path().data_dir() else { return }; // ~/.local/share
    // no AppImage, o executável é temporário: o atalho aponta para o próprio .AppImage
    let Some(exec) = std::env::var_os("APPIMAGE").map(PathBuf::from).or_else(|| std::env::current_exe().ok()) else { return };
    let desktop = base.join("applications").join(format!("{SERVICO}.desktop"));
    let conteudo = format!(
        "[Desktop Entry]\nType=Application\nName=FinTrix\nComment=Controle financeiro pessoal\nExec=\"{}\"\n\
         Icon={SERVICO}\nStartupWMClass={SERVICO}\nCategories=Office;Finance;\nTerminal=false\n",
        exec.display()
    );
    if fs::read_to_string(&desktop).ok().as_deref() != Some(conteudo.as_str()) {
        let _ = fs::create_dir_all(base.join("applications"));
        let _ = fs::write(&desktop, conteudo);
    }
    let icone = base.join("icons/hicolor/256x256/apps").join(format!("{SERVICO}.png"));
    if !icone.exists() {
        let _ = fs::create_dir_all(icone.parent().unwrap());
        let _ = fs::write(&icone, include_bytes!("../icons/128x128@2x.png"));
    }
}

fn abrir_banco(arquivo: &Path) -> Result<(Option<(Arc<Store>, String)>, Option<&'static str>), String> {
    let existe = arquivo.exists();
    Ok(match ler_chave() {
        Ok(Some(k)) => match Store::abrir(arquivo, &k) {
            Ok(s) => (Some((Arc::new(s), k)), None),
            Err(Erro::ChaveIncorreta) => (None, Some("chave-incorreta")),
            Err(e) => return Err(e.to_string()),
        },
        Ok(None) if !existe => {
            let k = gerar_chave().map_err(texto)?;
            guardar_chave(&k)?;
            (Some((Arc::new(Store::abrir(arquivo, &k).map_err(texto)?), k)), None)
        }
        Ok(None) => (None, Some("sem-chave")),
        Err(_) => (None, Some("sem-chaveiro")),
    })
}

/// Corpo cru: 4 bytes (u32 little-endian) com o tamanho de um JSON, o JSON e depois os bytes do arquivo.
fn quadro(corpo: &[u8]) -> Result<(Value, &[u8]), String> {
    let n = corpo.get(..4).map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]) as usize).ok_or("corpo curto")?;
    let meta = corpo.get(4..4 + n).ok_or("corpo curto")?;
    Ok((serde_json::from_slice(meta).map_err(texto)?, &corpo[4 + n..]))
}

#[tauri::command]
fn estado_banco(banco: State<Banco>) -> Value {
    let pronto = banco.aberto.read().map(|g| g.is_some()).unwrap_or(false);
    let motivo = *banco.motivo.read().unwrap();
    json!({ "pronto": pronto, "motivo": motivo, "existe": banco.arquivo.exists() })
}

/// Abre o banco com a chave de recuperação digitada e a guarda no chaveiro.
#[tauri::command]
fn informar_chave(banco: State<Banco>, chave: String) -> Result<Value, String> {
    let k: String = chave.chars().filter(char::is_ascii_hexdigit).collect::<String>().to_lowercase();
    if k.len() != 64 {
        return Err("A chave tem 64 caracteres (0-9 e a-f); confira o que foi digitado.".into());
    }
    if !banco.arquivo.exists() {
        return Err("Não há banco do FinTrix neste computador para abrir.".into());
    }
    let s = Store::abrir(&banco.arquivo, &k).map_err(|e| match e {
        Erro::ChaveIncorreta => "Chave incorreta para este banco.".to_string(),
        e => e.to_string(),
    })?;
    let salvo = guardar_chave(&k).is_ok();
    *banco.aberto.write().map_err(texto)? = Some((Arc::new(s), k));
    *banco.motivo.write().map_err(texto)? = None;
    Ok(json!({ "salvo": salvo }))
}

/// A chave em grupos de 4, para anotar ou imprimir.
#[tauri::command]
fn chave_recuperacao(banco: State<Banco>) -> Result<String, String> {
    let g = banco.aberto.read().map_err(texto)?;
    let (_, k) = g.as_ref().ok_or("banco trancado")?;
    Ok(k.as_bytes().chunks(4).map(|c| std::str::from_utf8(c).unwrap()).collect::<Vec<_>>().join("-"))
}

#[tauri::command]
fn db_todos(banco: State<Banco>) -> Result<Vec<(String, Value)>, String> {
    banco.store()?.todos().map_err(texto)
}

#[tauri::command]
fn db_gravar(banco: State<Banco>, sinc: State<Sincronia>, path: String, data: Option<Value>) -> Result<(), String> {
    banco.store()?.gravar(&path, data.as_ref()).map_err(texto)?;
    sinc.acordar.notify_one();
    Ok(())
}

#[tauri::command]
fn db_lote(banco: State<Banco>, sinc: State<Sincronia>, ops: Vec<Op>) -> Result<(), String> {
    banco.store()?.lote(&ops).map_err(texto)?;
    sinc.acordar.notify_one();
    Ok(())
}

// lojas: o que no navegador fica nos outros IndexedDB (cópias automáticas, comprovantes); veja lojaTauri em index.html
#[tauri::command]
fn loja_todos(banco: State<Banco>, loja: String) -> Result<Vec<Item>, String> {
    banco.store()?.loja_todos(&loja).map_err(texto)
}

#[tauri::command]
fn loja_get(banco: State<Banco>, loja: String, chave: Value) -> Result<Option<Item>, String> {
    banco.store()?.loja_get(&loja, &chave).map_err(texto)
}

/// Conteúdo do arquivo, como bytes crus (ArrayBuffer no JS).
#[tauri::command]
fn loja_bytes(banco: State<Banco>, loja: String, chave: Value) -> Result<Response, String> {
    match banco.store()?.loja_bytes(&loja, &chave).map_err(texto)? {
        Some(b) => Ok(Response::new(b)),
        None => Err("arquivo não encontrado".into()),
    }
}

#[tauri::command]
fn loja_gravar(banco: State<Banco>, loja: String, chave: Value, valor: Value) -> Result<(), String> {
    banco.store()?.loja_gravar(&loja, &chave, &valor, None).map_err(texto)
}

/// Corpo cru (`quadro`) com o JSON { loja, chave, valor } e o arquivo.
#[tauri::command]
fn loja_gravar_bytes(banco: State<Banco>, request: Request<'_>) -> Result<(), String> {
    let InvokeBody::Raw(corpo) = request.body() else {
        return Err("esperava bytes".into());
    };
    let (meta, arq) = quadro(corpo)?;
    let (Some(loja), Some(chave), Some(valor)) = (meta["loja"].as_str(), meta.get("chave"), meta.get("valor")) else {
        return Err("cabeçalho incompleto".into());
    };
    banco.store()?.loja_gravar(loja, chave, valor, Some(arq)).map_err(texto)
}

#[tauri::command]
fn loja_adicionar(banco: State<Banco>, loja: String, valor: Value) -> Result<i64, String> {
    banco.store()?.loja_adicionar(&loja, &valor).map_err(texto)
}

#[tauri::command]
fn loja_apagar(banco: State<Banco>, loja: String, chave: Value) -> Result<(), String> {
    banco.store()?.loja_apagar(&loja, &chave).map_err(texto)
}

#[tauri::command]
fn loja_limpar(banco: State<Banco>, loja: String) -> Result<(), String> {
    banco.store()?.loja_limpar(&loja).map_err(texto)
}

/// Backup, CSV, .zip e comprovantes: corpo cru (`quadro`) com o JSON { nome } e o conteúdo.
/// Abre a janela "Salvar como" do sistema; devolve o caminho gravado, ou null se a pessoa cancelou.
#[tauri::command]
async fn salvar_arquivo(app: AppHandle, request: Request<'_>) -> Result<Option<String>, String> {
    let InvokeBody::Raw(corpo) = request.body() else {
        return Err("esperava bytes".into());
    };
    let (meta, dados) = quadro(corpo)?;
    // só o nome, nunca um caminho vindo da página
    let nome = Path::new(meta["nome"].as_str().unwrap_or("arquivo"))
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("arquivo")
        .to_string();
    #[cfg(debug_assertions)]
    if let Some(d) = std::env::var_os("FINTRIX_SALVAR_EM") {
        let p = PathBuf::from(d).join(&nome);
        fs::write(&p, dados).map_err(texto)?;
        return Ok(Some(p.display().to_string()));
    }
    // no Android o seletor devolve um content://, que into_path não aceita (etapa 4 de docs/android.md)
    let Some(escolhido) = app.dialog().file().set_file_name(&nome).blocking_save_file() else {
        return Ok(None);
    };
    let p = escolhido.into_path().map_err(texto)?;
    fs::write(&p, dados).map_err(texto)?;
    Ok(Some(p.display().to_string()))
}

// ---------- sincronização (veja fintrix_core::sync)

/// Um ciclo agora. Avisa a interface dos documentos que mudaram ("db-remoto") e do estado ("sync-estado").
async fn ciclo(app: &AppHandle) -> Result<Value, String> {
    let sinc = app.state::<Sincronia>();
    let _vez = sinc.rodando.lock().await;
    let _ = app.emit("sync-estado", estado_sync(app)); // a tela mostra "sincronizando…"
    let store = app.state::<Banco>().store()?;
    let Some(cofre) = sync::cofre_salvo(&store).map_err(texto)? else { return Ok(json!({ "ligado": false })) };
    let Some(versao) = *sinc.versao.lock().unwrap() else { return Err("a interface ainda não abriu".into()) };
    let r = sync::sincronizar(&store, &cofre, versao).await;
    let res = match r {
        Ok(rel) => {
            if !rel.alterados.is_empty() {
                let _ = app.emit("db-remoto", &rel.alterados);
            }
            *sinc.erro.lock().unwrap() = None;
            *sinc.outros.lock().unwrap() = rel.outros_aparelhos;
            Ok(json!({ "alterados": rel.alterados.len(), "enviou": rel.enviou, "anexosEnviados": rel.anexos_enviados, "anexosBaixados": rel.anexos_baixados }))
        }
        Err(e) => {
            *sinc.erro.lock().unwrap() = Some(e.to_string());
            Err(e.to_string())
        }
    };
    let _ = app.emit("sync-estado", estado_sync(app));
    res
}

fn estado_sync(app: &AppHandle) -> Value {
    let sinc = app.state::<Sincronia>();
    let Ok(store) = app.state::<Banco>().store() else { return json!({ "ligado": false }) };
    let cofre = sync::cofre_salvo(&store).ok().flatten();
    let ultimo = store.meta("sync/ultimo").ok().flatten().and_then(|v| v.parse::<u64>().ok());
    json!({
        "ligado": cofre.is_some(),
        "tipo": cofre.as_ref().map(|c| match c.destino { Destino::Pasta { .. } => "pasta", Destino::S3 { .. } => "s3" }),
        "destino": cofre.as_ref().map(|c| c.destino.descricao()),
        "ultimo": ultimo,
        "erro": *sinc.erro.lock().unwrap(),
        "outros": *sinc.outros.lock().unwrap(),
        "sincronizando": sinc.rodando.try_lock().is_err(),
    })
}

/// Sincroniza a cada minuto e alguns segundos depois de cada gravação local.
async fn sincronizar_sempre(app: AppHandle) {
    loop {
        let sinc = app.state::<Sincronia>();
        let _ = tokio::time::timeout(std::time::Duration::from_secs(60), sinc.acordar.notified()).await;
        // junta gravações seguidas num envio só
        tokio::time::sleep(std::time::Duration::from_secs(4)).await;
        let _ = ciclo(&app).await;
    }
}

#[tauri::command]
fn sync_estado(app: AppHandle) -> Value {
    estado_sync(&app)
}

/// A interface informa a versão de dados que entende e pede um ciclo (ao abrir e no botão "Sincronizar agora").
#[tauri::command]
async fn sync_agora(app: AppHandle, versao: u32) -> Result<Value, String> {
    *app.state::<Sincronia>().versao.lock().unwrap() = Some(versao);
    ciclo(&app).await
}

/// Cria um cofre com os dados deste aparelho e começa o primeiro envio. Devolve { codigo, enviando }.
/// O primeiro envio (estado e todos os comprovantes) pode levar minutos num bucket: espera até 15 s para
/// pegar os erros rápidos (chave, endpoint, bucket); depois disso devolve o código e o envio continua em
/// segundo plano, com o andamento no status. Se esse primeiro envio falhar, a sincronização é desligada.
#[tauri::command]
async fn sync_criar(app: AppHandle, destino: Destino, versao: u32) -> Result<Value, String> {
    let store = app.state::<Banco>().store()?;
    let cofre = Cofre::novo(destino).map_err(texto)?;
    sync::conectar(&cofre.destino).map_err(texto)?;
    sync::salvar_cofre(&store, Some(&cofre)).map_err(texto)?;
    *app.state::<Sincronia>().versao.lock().unwrap() = Some(versao);
    let codigo = cofre.codigo().map_err(texto)?;
    let app2 = app.clone();
    let mut primeiro = tauri::async_runtime::spawn(async move {
        let r = ciclo(&app2).await;
        if let Err(e) = &r {
            // nunca chegou a sincronizar: desfaz, para a tela voltar a oferecer "Ligar" com o motivo
            if let Ok(store) = app2.state::<Banco>().store() {
                if store.meta("sync/ultimo").ok().flatten().is_none() {
                    let _ = sync::salvar_cofre(&store, None);
                    *app2.state::<Sincronia>().erro.lock().unwrap() = Some(format!("A sincronização não foi ligada: {e}"));
                    let _ = app2.emit("sync-estado", estado_sync(&app2));
                }
            }
        }
        r
    });
    match tokio::time::timeout(std::time::Duration::from_secs(15), &mut primeiro).await {
        Ok(Ok(Ok(_))) => Ok(json!({ "codigo": codigo, "enviando": false })),
        Ok(Ok(Err(e))) => Err(e),
        Ok(Err(e)) => Err(e.to_string()),
        Err(_) => Ok(json!({ "codigo": codigo, "enviando": true })),
    }
}

/// Entra num cofre existente: confere o código e o destino ANTES de trocar os dados deste aparelho pelos do cofre.
/// `pasta`: no destino do tipo pasta, onde ela está neste aparelho (cada um tem o seu caminho).
#[tauri::command]
async fn sync_entrar(app: AppHandle, codigo: String, pasta: Option<String>, versao: u32) -> Result<Value, String> {
    let store = app.state::<Banco>().store()?;
    let mut cofre = Cofre::do_codigo(&codigo).map_err(texto)?;
    if let (Destino::Pasta { pasta: p }, Some(nova)) = (&mut cofre.destino, pasta.filter(|x| !x.trim().is_empty())) {
        *p = nova;
    }
    let aparelhos = sync::verificar(&cofre).await.map_err(texto)?;
    store.esvaziar_documentos().map_err(texto)?;
    sync::salvar_cofre(&store, Some(&cofre)).map_err(texto)?;
    *app.state::<Sincronia>().versao.lock().unwrap() = Some(versao);
    let r = ciclo(&app).await?;
    Ok(json!({ "aparelhos": aparelhos, "ciclo": r }))
}

/// Código de pareamento do cofre ligado (tem os segredos: mostrar só a quem vai parear).
#[tauri::command]
fn sync_codigo(banco: State<Banco>) -> Result<String, String> {
    let store = banco.store()?;
    let c = sync::cofre_salvo(&store).map_err(texto)?.ok_or("a sincronização está desligada")?;
    c.codigo().map_err(texto)
}

/// Desliga neste aparelho. Os dados continuam aqui e no cofre.
#[tauri::command]
fn sync_desligar(app: AppHandle) -> Result<Value, String> {
    let store = app.state::<Banco>().store()?;
    sync::salvar_cofre(&store, None).map_err(texto)?;
    *app.state::<Sincronia>().erro.lock().unwrap() = None;
    Ok(estado_sync(&app))
}

#[cfg(desktop)]
#[tauri::command]
async fn escolher_pasta(app: AppHandle) -> Result<Option<String>, String> {
    let Some(p) = app.dialog().file().blocking_pick_folder() else { return Ok(None) };
    Ok(Some(p.into_path().map_err(texto)?.display().to_string()))
}

/// No celular a sincronização é só por bucket: o app não enxerga a pasta do Syncthing pelo caminho.
#[cfg(mobile)]
#[tauri::command]
async fn escolher_pasta() -> Result<Option<String>, String> {
    Err("No celular, a sincronização é só por bucket S3.".into())
}

/// Fim de um roteiro de teste (FINTRIX_TESTE): imprime o relatório e fecha o app. Sem efeito em release.
#[tauri::command]
fn teste_fim(app: AppHandle, ok: bool, relatorio: String) {
    if cfg!(debug_assertions) && std::env::var_os("FINTRIX_TESTE").is_some() {
        println!("{relatorio}");
        app.exit(if ok { 0 } else { 1 });
    }
}

fn contexto() -> tauri::Context {
    #[allow(unused_mut)]
    let mut ctx = tauri::generate_context!();
    // testes (só em debug, com pasta própria): sem instância única, para rodar com o FinTrix do usuário aberto
    #[cfg(debug_assertions)]
    if std::env::var_os("FINTRIX_DADOS").is_some() {
        ctx.config_mut().app.enable_gtk_app_id = false;
    }
    ctx
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // no Wayland, o app_id da janela é o nome do programa: com o identificador, ele casa com o .desktop e o ícone
    #[cfg(target_os = "linux")]
    glib::set_prgname(Some(SERVICO));
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let dir = pasta_de_dados(app.handle())?;
            fs::create_dir_all(&dir)?;
            restringir(&dir);
            #[cfg(desktop)]
            migrar_do_antigo(app.handle(), &dir);
            #[cfg(target_os = "linux")]
            registrar_atalho(app.handle());
            let arquivo = dir.join("fintrix.db");
            let (aberto, motivo) = abrir_banco(&arquivo)?;
            app.manage(Banco { arquivo, aberto: RwLock::new(aberto), motivo: RwLock::new(motivo) });
            app.manage(Sincronia::default());
            tauri::async_runtime::spawn(sincronizar_sempre(app.handle().clone()));
            #[allow(unused_mut)]
            let mut janela = WebviewWindowBuilder::new(app, "main", WebviewUrl::default()).title("FinTrix");
            // no celular a janela é a tela toda, com o ícone do app e a pasta da WebView do sistema
            #[cfg(desktop)]
            {
                // no X11 (e no Windows) o ícone vem daqui; no Wayland, do .desktop (registrar_atalho)
                if let Some(icone) = app.default_window_icon() {
                    janela = janela.icon(icone.clone())?;
                }
                // a WebView guarda o que é dela (preferências da tela) junto com o banco
                janela = janela.inner_size(1200.0, 800.0).min_inner_size(380.0, 600.0).data_directory(dir.join("webview"));
            }
            janela.build()?;
            Ok(())
        })
        .on_page_load(|webview, payload| {
            if !cfg!(debug_assertions) || payload.event() != PageLoadEvent::Finished {
                return;
            }
            if let Some(roteiro) = std::env::var_os("FINTRIX_TESTE") {
                match fs::read_to_string(&roteiro) {
                    Ok(js) => {
                        let _ = webview.eval(&js);
                    }
                    Err(e) => {
                        eprintln!("roteiro de teste ilegível: {e}");
                        webview.app_handle().exit(2);
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            estado_banco,
            informar_chave,
            chave_recuperacao,
            db_todos,
            db_gravar,
            db_lote,
            loja_todos,
            loja_get,
            loja_bytes,
            loja_gravar,
            loja_gravar_bytes,
            loja_adicionar,
            loja_apagar,
            loja_limpar,
            salvar_arquivo,
            sync_estado,
            sync_agora,
            sync_criar,
            sync_entrar,
            sync_codigo,
            sync_desligar,
            escolher_pasta,
            teste_fim
        ])
        .run(contexto())
        .expect("erro ao iniciar o FinTrix");
}
