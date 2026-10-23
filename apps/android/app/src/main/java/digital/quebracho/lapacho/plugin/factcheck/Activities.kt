package digital.quebracho.lapacho.plugin.factcheck

import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File
import uniffi.factcheck_bridge.Checker
import uniffi.factcheck_bridge.FactcheckException

/** Lapacho's plugin-app contract (docs/PLUGINS.md in Lapacho). */
object Contract {
    const val EXTRA_TEXT = "digital.quebracho.lapacho.extra.TEXT"
    const val EXTRA_ERROR = "digital.quebracho.lapacho.extra.ERROR"
}

const val DEFAULT_MODEL_URL =
    "https://huggingface.co/quebracho-digital/gemma-4-E2B-it-factcheck/resolve/main/gemma-4-E2B-it-factcheck-Q4_K_M.gguf"

/**
 * ponytail: plain app-private preferences, the SerpApi key included; only this
 * app can read them. Android's Keystore is the upgrade if the key ever guards more.
 */
private class Settings(private val context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    var serpapiKey: String
        get() = prefs.getString("serpapi_key", "").orEmpty()
        set(v) = prefs.edit().putString("serpapi_key", v.trim()).apply()
    /** The trusted.txt text; the demo list until the user saves their own. */
    var trusted: String
        get() = prefs.getString("trusted", null)
            ?: context.assets.open("trusted-mbfc.txt").bufferedReader().use { it.readText() }
        set(v) = prefs.edit().putString("trusted", v).apply()
    var modelUrl: String
        get() = prefs.getString("model_url", DEFAULT_MODEL_URL).orEmpty()
        set(v) = prefs.edit().putString("model_url", v.trim()).apply()
    var downloadId: Long
        get() = prefs.getLong("download_id", -1)
        set(v) = prefs.edit().putLong("download_id", v).apply()

    /** The GGUF, in the app's own folder: no storage permission, gone on uninstall. */
    val model: File get() = File(context.getExternalFilesDir(null), "model.gguf")
    val partial: File get() = File(context.getExternalFilesDir(null), "model.gguf.part")
}

/** The model stays loaded while the process lives: loading takes seconds, a check is run many times. */
private object Model {
    private var loaded: Pair<String, Checker>? = null

    @Synchronized
    fun get(file: File): Checker {
        val key = "${file.path}:${file.lastModified()}"
        loaded?.let { (k, c) -> if (k == key) return c }
        loaded = null
        return Checker(file.path).also { loaded = key to it }
    }
}

private fun Activity.dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).toInt()

private fun Activity.column(): LinearLayout = LinearLayout(this).apply {
    orientation = LinearLayout.VERTICAL
    val pad = dp(20f)
    setPadding(pad, pad * 2, pad, pad)
}

private fun Activity.scrolling(content: LinearLayout) = ScrollView(this).apply { addView(content) }

/** The launcher screen: the SerpApi key, the trusted sites, the model. */
class SettingsActivity : Activity() {
    private lateinit var s: Settings
    private lateinit var modelStatus: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        s = Settings(this)
        val root = column()
        root.addView(TextView(this).apply { setText(R.string.settings_intro) })

        root.addView(TextView(this).apply { setText(R.string.label_key) })
        val key = EditText(this).apply {
            setText(s.serpapiKey)
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            root.addView(this)
        }

        root.addView(TextView(this).apply { setText(R.string.label_trusted) })
        val trusted = EditText(this).apply {
            setText(s.trusted)
            typeface = Typeface.MONOSPACE
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            gravity = Gravity.TOP
            minLines = 6
            maxLines = 14
            root.addView(this)
        }

        root.addView(TextView(this).apply { setText(R.string.label_model) })
        modelStatus = TextView(this).also { root.addView(it) }
        val url = EditText(this).apply {
            setText(s.modelUrl)
            isSingleLine = true
            root.addView(this)
        }
        root.addView(Button(this).apply {
            setText(R.string.download_model)
            setOnClickListener { download(url.text.toString().trim()) }
        })

        root.addView(Button(this).apply {
            setText(R.string.save)
            setOnClickListener {
                s.serpapiKey = key.text.toString()
                s.trusted = trusted.text.toString()
                s.modelUrl = url.text.toString()
                Toast.makeText(this@SettingsActivity, R.string.saved, Toast.LENGTH_SHORT).show()
            }
        })
        setContentView(scrolling(root))
    }

    override fun onResume() {
        super.onResume()
        refreshModel()
    }

    /** Where the download is; a finished one is renamed into place. */
    private fun refreshModel() {
        val dm = getSystemService(DownloadManager::class.java)
        val id = s.downloadId
        if (id >= 0) {
            dm.query(DownloadManager.Query().setFilterById(id))?.use { c ->
                if (c.moveToFirst()) {
                    val status = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    val done = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                    val total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                    when (status) {
                        DownloadManager.STATUS_SUCCESSFUL -> {
                            s.model.delete()
                            s.partial.renameTo(s.model)
                            s.downloadId = -1
                        }
                        DownloadManager.STATUS_FAILED -> {
                            s.downloadId = -1
                            return modelStatus.setText(R.string.model_failed)
                        }
                        else -> return run {
                            modelStatus.text = getString(R.string.model_downloading, done / 1_000_000, maxOf(total, 0) / 1_000_000)
                        }
                    }
                }
            }
        }
        modelStatus.text = if (s.model.isFile) {
            getString(R.string.model_ready, s.model.length() / 1_000_000)
        } else {
            getString(R.string.model_missing)
        }
    }

    private fun download(url: String) {
        if (!url.startsWith("https://")) return Toast.makeText(this, R.string.err_url, Toast.LENGTH_LONG).show()
        s.modelUrl = url
        s.partial.delete()
        val request = DownloadManager.Request(Uri.parse(url))
            .setTitle(getString(R.string.app_name))
            .setDestinationUri(Uri.fromFile(s.partial))
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
        s.downloadId = getSystemService(DownloadManager::class.java).enqueue(request)
        refreshModel()
    }
}

/**
 * What Lapacho opens with a clip. Writes the queries on the phone and shows
 * them before anything leaves it, so they can be edited or the check
 * cancelled; then searches, reads the results and hands the verdict back.
 * Leaving the screen cancels: the result is dropped (the native call itself
 * finishes in the background).
 */
class RunActivity : Activity() {
    @Volatile private var cancelled = false
    private lateinit var s: Settings
    private lateinit var root: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        s = Settings(this)
        val clip = intent.getStringExtra(Contract.EXTRA_TEXT)
        if (clip.isNullOrBlank()) return fail(getString(R.string.err_nothing))
        if (s.serpapiKey.isBlank() || !s.model.isFile) {
            Toast.makeText(this, R.string.err_not_configured, Toast.LENGTH_LONG).show()
            startActivity(Intent(this, SettingsActivity::class.java))
            return fail(getString(R.string.err_not_configured))
        }
        root = column()
        setContentView(scrolling(root))
        working(R.string.writing_queries)
        background({ Model.get(s.model).queries(clip) }) { queries -> confirm(clip, queries) }
    }

    /** The queries, editable, before anything is sent. */
    private fun confirm(clip: String, queries: List<String>) {
        root.removeAllViews()
        root.addView(TextView(this).apply { setText(R.string.confirm_queries) })
        val edit = EditText(this).apply {
            setText(queries.joinToString("\n"))
            gravity = Gravity.TOP
            minLines = 3
            root.addView(this)
        }
        root.addView(Button(this).apply {
            setText(R.string.search)
            setOnClickListener {
                val qs = edit.text.lines().map { it.trim() }.filter { it.isNotEmpty() }
                if (qs.isEmpty()) return@setOnClickListener
                working(R.string.searching)
                background({ Model.get(s.model).check(clip, qs, s.serpapiKey, s.trusted) }) { verdict ->
                    setResult(RESULT_OK, Intent().putExtra(Contract.EXTRA_TEXT, verdict))
                    finish()
                }
            }
        })
        root.addView(cancelButton())
    }

    private fun working(message: Int) {
        root.removeAllViews()
        root.gravity = Gravity.CENTER_HORIZONTAL
        root.addView(ProgressBar(this))
        root.addView(TextView(this).apply {
            setText(message)
            gravity = Gravity.CENTER
        })
        root.addView(cancelButton())
    }

    private fun cancelButton() = Button(this).apply {
        setText(android.R.string.cancel)
        setOnClickListener { cancelled = true; fail(getString(R.string.err_cancelled)) }
    }

    private fun <T> background(work: () -> T, then: (T) -> Unit) {
        Thread {
            val result = runCatching(work)
            runOnUiThread {
                if (cancelled || isFinishing) return@runOnUiThread
                result.fold(
                    onSuccess = then,
                    onFailure = { e ->
                        fail((e as? FactcheckException.Failed)?.reason ?: e.message ?: e.javaClass.simpleName)
                    },
                )
            }
        }.start()
    }

    private fun fail(message: String) {
        setResult(RESULT_CANCELED, Intent().putExtra(Contract.EXTRA_ERROR, message))
        finish()
    }
}
