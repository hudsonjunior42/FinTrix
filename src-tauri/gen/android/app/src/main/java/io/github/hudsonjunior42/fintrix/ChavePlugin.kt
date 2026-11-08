package io.github.hudsonjunior42.fintrix

import android.app.Activity
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import app.tauri.annotation.Command
import app.tauri.annotation.InvokeArg
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.JSObject
import app.tauri.plugin.Plugin
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

@InvokeArg
class GuardarArgs {
    lateinit var chave: String
}

/**
 * Chaveiro do celular: a chave do banco (SQLCipher) fica num arquivo da pasta privada do app,
 * cifrada com AES-GCM por uma chave do Android Keystore que nunca sai do aparelho.
 * Só o Rust chama (chaveiro::ler / chaveiro::guardar em lib.rs); nunca registrar valores em log.
 */
@TauriPlugin
class ChavePlugin(private val activity: Activity) : Plugin(activity) {
    private companion object {
        const val APELIDO = "fintrix-chave-do-banco"
        const val CIFRA = "AES/GCM/NoPadding"
        const val TAM_IV = 12
    }

    // fora do backup do Android: sem a chave do Keystore, que não vai junto, o arquivo não serve para nada
    private val arquivo get() = File(activity.noBackupFilesDir, "chave-do-banco.bin")

    private fun mestra(criar: Boolean): SecretKey? {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(APELIDO, null) as? SecretKey)?.let { return it }
        if (!criar) return null
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(APELIDO, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return gen.generateKey()
    }

    /** { chave: "…" } ou {} quando não há chave guardada (app novo, ou a chave do Keystore sumiu). */
    @Command
    fun ler(invoke: Invoke) {
        try {
            val r = JSObject()
            val f = arquivo
            val m = mestra(false)
            if (f.exists() && m != null) {
                val b = f.readBytes()
                val c = Cipher.getInstance(CIFRA)
                c.init(Cipher.DECRYPT_MODE, m, GCMParameterSpec(128, b, 0, TAM_IV))
                r.put("chave", String(c.doFinal(b, TAM_IV, b.size - TAM_IV), Charsets.UTF_8))
            }
            invoke.resolve(r)
        } catch (e: Exception) {
            invoke.reject("não foi possível ler a chave guardada (${e.javaClass.simpleName})")
        }
    }

    @Command
    fun guardar(invoke: Invoke) {
        try {
            val args = invoke.parseArgs(GuardarArgs::class.java)
            val c = Cipher.getInstance(CIFRA)
            c.init(Cipher.ENCRYPT_MODE, mestra(true))
            val tmp = File(arquivo.path + ".novo")
            tmp.writeBytes(c.iv + c.doFinal(args.chave.toByteArray(Charsets.UTF_8)))
            if (!tmp.renameTo(arquivo)) throw IllegalStateException("renameTo")
            invoke.resolve()
        } catch (e: Exception) {
            invoke.reject("não foi possível guardar a chave (${e.javaClass.simpleName})")
        }
    }
}
