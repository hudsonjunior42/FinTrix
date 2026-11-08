// evita a janela de console extra no Windows em release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;

use fintrix_core::{gerar_chave, Op, Store};
use serde_json::Value;
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
        .invoke_handler(tauri::generate_handler![db_todos, db_gravar, db_lote, teste_fim])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o FinTrix");
}
