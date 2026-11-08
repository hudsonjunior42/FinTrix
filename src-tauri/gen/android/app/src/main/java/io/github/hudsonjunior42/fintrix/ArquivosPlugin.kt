package io.github.hudsonjunior42.fintrix

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import androidx.core.content.FileProvider
import app.tauri.annotation.Command
import app.tauri.annotation.InvokeArg
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.Plugin
import java.io.File

@InvokeArg
class AbrirArgs {
    lateinit var caminho: String
    var tipo: String? = null
}

/**
 * Abre um arquivo no app do sistema (PDF de comprovante, que a WebView não mostra). O Rust grava a cópia em
 * cache/abrir/ (abrir_arquivo em lib.rs) e aqui ela vai por FileProvider, com permissão só de leitura e só
 * para o app escolhido.
 */
@TauriPlugin
class ArquivosPlugin(private val activity: Activity) : Plugin(activity) {
    @Command
    fun abrir(invoke: Invoke) {
        try {
            val args = invoke.parseArgs(AbrirArgs::class.java)
            val arq = File(args.caminho)
            if (arq.parentFile?.canonicalPath != File(activity.cacheDir, "abrir").canonicalPath) {
                throw SecurityException("arquivo fora da pasta de abrir")
            }
            val uri = FileProvider.getUriForFile(activity, activity.packageName + ".fileprovider", arq)
            val intent = Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, args.tipo ?: "application/octet-stream")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            activity.startActivity(intent)
            invoke.resolve()
        } catch (e: ActivityNotFoundException) {
            invoke.reject("Nenhum app deste celular abre esse tipo de arquivo.")
        } catch (e: Exception) {
            invoke.reject("Não foi possível abrir o arquivo (${e.javaClass.simpleName}).")
        }
    }
}
