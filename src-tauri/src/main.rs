// evita a janela de console extra no Windows em release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;

use fintrix_core::{gerar_chave, Item, Op, Store};
use serde_json::Value;
use tauri::ipc::{InvokeBody, Request, Response};
use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Manager, State, WebviewUrl, WebviewWindowBuilder};

const SERVICO: &str = "br.com.fintrix.app";
const USUARIO: &str = "chave-do-banco";

/// Lê a chave do banco no chaveiro do sistema; na primeira execução gera e guarda uma.
/// A chave nunca vai para o disco em texto puro: sem chaveiro disponível o app não abre.
fn chave_do_banco(banco_existe: bool) -> Result<String, String> {
    // testes (só em debug): chave e pasta vêm do ambiente, sem tocar no chaveiro real
    #[cfg(debug_assertions)]
    if let Ok(k) = std::env::var("FINTRIX_CHAVE") {
        return Ok(k);
    }
    let entrada = keyring::Entry::new(SERVICO, USUARIO).map_err(|e| e.to_string())?;
    match entrada.get_password() {
        Ok(k) => Ok(k),
        Err(keyring::Error::NoEntry) if !banco_existe => {
            let k = gerar_chave().map_err(|e| e.to_string())?;
            entrada.set_password(&k).map_err(|e| e.to_string())?;
            Ok(k)
        }
        Err(keyring::Error::NoEntry) => Err(
            "O banco existe, mas a chave não está no chaveiro do sistema. \
             Restaure a chave ou um backup."
                .into(),
        ),
        Err(e) => Err(format!("chaveiro do sistema indisponível: {e}")),
    }
}

fn pasta_de_dados(app: &AppHandle) -> tauri::Result<PathBuf> {
    #[cfg(debug_assertions)]
    if let Some(d) = std::env::var_os("FINTRIX_DADOS") {
        return Ok(PathBuf::from(d));
    }
    app.path().app_data_dir()
}

#[tauri::command]
fn db_todos(store: State<Store>) -> Result<Vec<(String, Value)>, String> {
    store.todos().map_err(|e| e.to_string())
}

#[tauri::command]
fn db_gravar(store: State<Store>, path: String, data: Option<Value>) -> Result<(), String> {
    store.gravar(&path, data.as_ref()).map_err(|e| e.to_string())
}

#[tauri::command]
fn db_lote(store: State<Store>, ops: Vec<Op>) -> Result<(), String> {
    store.lote(&ops).map_err(|e| e.to_string())
}

// lojas: o que no navegador fica nos outros IndexedDB (cópias automáticas, comprovantes); veja lojaTauri em index.html
#[tauri::command]
fn loja_todos(store: State<Store>, loja: String) -> Result<Vec<Item>, String> {
    store.loja_todos(&loja).map_err(|e| e.to_string())
}

#[tauri::command]
fn loja_get(store: State<Store>, loja: String, chave: Value) -> Result<Option<Item>, String> {
    store.loja_get(&loja, &chave).map_err(|e| e.to_string())
}

/// Conteúdo do arquivo, como bytes crus (ArrayBuffer no JS).
#[tauri::command]
fn loja_bytes(store: State<Store>, loja: String, chave: Value) -> Result<Response, String> {
    match store.loja_bytes(&loja, &chave).map_err(|e| e.to_string())? {
        Some(b) => Ok(Response::new(b)),
        None => Err("arquivo não encontrado".into()),
    }
}

#[tauri::command]
fn loja_gravar(store: State<Store>, loja: String, chave: Value, valor: Value) -> Result<(), String> {
    store.loja_gravar(&loja, &chave, &valor, None).map_err(|e| e.to_string())
}

/// Corpo cru: 4 bytes (u32 little-endian) com o tamanho do JSON { loja, chave, valor }, o JSON e depois o arquivo.
#[tauri::command]
fn loja_gravar_bytes(store: State<Store>, request: Request<'_>) -> Result<(), String> {
    let InvokeBody::Raw(corpo) = request.body() else {
        return Err("esperava bytes".into());
    };
    let n = corpo.get(..4).map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]) as usize).ok_or("corpo curto")?;
    let meta = corpo.get(4..4 + n).ok_or("corpo curto")?;
    let meta: Value = serde_json::from_slice(meta).map_err(|e| e.to_string())?;
    let (Some(loja), Some(chave), Some(valor)) = (meta["loja"].as_str(), meta.get("chave"), meta.get("valor")) else {
        return Err("cabeçalho incompleto".into());
    };
    store.loja_gravar(loja, chave, valor, Some(&corpo[4 + n..])).map_err(|e| e.to_string())
}

#[tauri::command]
fn loja_adicionar(store: State<Store>, loja: String, valor: Value) -> Result<i64, String> {
    store.loja_adicionar(&loja, &valor).map_err(|e| e.to_string())
}

#[tauri::command]
fn loja_apagar(store: State<Store>, loja: String, chave: Value) -> Result<(), String> {
    store.loja_apagar(&loja, &chave).map_err(|e| e.to_string())
}

#[tauri::command]
fn loja_limpar(store: State<Store>, loja: String) -> Result<(), String> {
    store.loja_limpar(&loja).map_err(|e| e.to_string())
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
    tauri::Builder::default()
        .setup(|app| {
            let dir = pasta_de_dados(app.handle())?;
            fs::create_dir_all(&dir)?;
            let arquivo = dir.join("fintrix.db");
            let chave = chave_do_banco(arquivo.exists())?;
            app.manage(Store::abrir(&arquivo, &chave)?);
            // a WebView guarda o que é dela (preferências, comprovantes) junto com o banco
            WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("FinTrix")
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
            teste_fim
        ])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o FinTrix");
}
