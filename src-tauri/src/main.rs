// evita a janela de console extra no Windows em release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;

use fintrix_core::{gerar_chave, Op, Store};
use serde_json::Value;
use tauri::{Manager, State};

const SERVICO: &str = "br.com.fintrix.app";
const USUARIO: &str = "chave-do-banco";

/// Lê a chave do banco no chaveiro do sistema; na primeira execução gera e guarda uma.
/// A chave nunca vai para o disco em texto puro: sem chaveiro disponível o app não abre.
fn chave_do_banco(banco_existe: bool) -> Result<String, String> {
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

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let dir = app.path().app_data_dir()?;
            fs::create_dir_all(&dir)?;
            let arquivo = dir.join("fintrix.db");
            let chave = chave_do_banco(arquivo.exists())?;
            app.manage(Store::abrir(&arquivo, &chave)?);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![db_todos, db_gravar, db_lote])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o FinTrix");
}
