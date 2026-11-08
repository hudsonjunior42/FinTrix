// evita a janela de console extra no Windows em release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, RwLock};

use fintrix_core::{gerar_chave, Erro, Item, Op, Store};
use serde_json::{json, Value};
use tauri::ipc::{InvokeBody, Request, Response};
use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Manager, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

/// Igual ao `identifier` do tauri.conf.json: nome do serviço no chaveiro e da pasta de dados.
const SERVICO: &str = "io.github.hudsonjunior42.fintrix";
/// Identificador das primeiras versões do protótipo; os dados de lá são trazidos uma vez.
const ANTIGO: &str = "br.com.fintrix.app";
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
    match keyring::Entry::new(SERVICO, USUARIO).map_err(texto)?.get_password() {
        Ok(k) => Ok(Some(k)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(format!("chaveiro do sistema indisponível: {e}")),
    }
}

fn guardar_chave(k: &str) -> Result<(), String> {
    #[cfg(debug_assertions)]
    if std::env::var_os("FINTRIX_CHAVE").is_some() {
        return Ok(());
    }
    keyring::Entry::new(SERVICO, USUARIO).map_err(texto)?.set_password(k).map_err(texto)
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
fn db_gravar(banco: State<Banco>, path: String, data: Option<Value>) -> Result<(), String> {
    banco.store()?.gravar(&path, data.as_ref()).map_err(texto)
}

#[tauri::command]
fn db_lote(banco: State<Banco>, ops: Vec<Op>) -> Result<(), String> {
    banco.store()?.lote(&ops).map_err(texto)
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
    let Some(escolhido) = app.dialog().file().set_file_name(&nome).blocking_save_file() else {
        return Ok(None);
    };
    let p = escolhido.into_path().map_err(texto)?;
    fs::write(&p, dados).map_err(texto)?;
    Ok(Some(p.display().to_string()))
}

/// Fim de um roteiro de teste (FINTRIX_TESTE): imprime o relatório e fecha o app. Sem efeito em release.
#[tauri::command]
fn teste_fim(app: AppHandle, ok: bool, relatorio: String) {
    if cfg!(debug_assertions) && std::env::var_os("FINTRIX_TESTE").is_some() {
        println!("{relatorio}");
        app.exit(if ok { 0 } else { 1 });
    }
}

fn main() {
    // no Wayland, o app_id da janela é o nome do programa: com o identificador, ele casa com o .desktop e o ícone
    #[cfg(target_os = "linux")]
    glib::set_prgname(Some(SERVICO));
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let dir = pasta_de_dados(app.handle())?;
            fs::create_dir_all(&dir)?;
            restringir(&dir);
            migrar_do_antigo(app.handle(), &dir);
            #[cfg(target_os = "linux")]
            registrar_atalho(app.handle());
            let arquivo = dir.join("fintrix.db");
            let (aberto, motivo) = abrir_banco(&arquivo)?;
            app.manage(Banco { arquivo, aberto: RwLock::new(aberto), motivo: RwLock::new(motivo) });
            // a WebView guarda o que é dela (preferências da tela) junto com o banco
            let mut janela = WebviewWindowBuilder::new(app, "main", WebviewUrl::default()).title("FinTrix");
            // no X11 (e no Windows) o ícone vem daqui; no Wayland, do .desktop (registrar_atalho)
            if let Some(icone) = app.default_window_icon() {
                janela = janela.icon(icone.clone())?;
            }
            janela
                .inner_size(1200.0, 800.0)
                .min_inner_size(380.0, 600.0)
                .data_directory(dir.join("webview"))
                .build()?;
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
            teste_fim
        ])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o FinTrix");
}
