package app.memorypal.liveaudio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import java.util.concurrent.LinkedBlockingQueue
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

// A voice-call style audio set-up: the microphone uses the VOICE_COMMUNICATION
// source with the platform echo canceller, and speech plays as a call, so the
// tutor's voice on the loudspeaker isn't heard as the learner talking over it.
// Based on @speechmatics/expo-two-way-audio (MIT), trimmed down, with a
// 24 kHz player and clear() for interruptions.
class LiveAudioEngine(context: Context) {
  private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
  private var record: AudioRecord? = null
  private var track: AudioTrack? = null
  private var echoCanceler: AcousticEchoCanceler? = null
  private var noiseSuppressor: NoiseSuppressor? = null
  private var focus: AudioFocusRequest? = null
  private val speech = LinkedBlockingQueue<ByteArray>()
  private var micThread: Thread? = null
  private var playThread: Thread? = null
  private var previousMode = AudioManager.MODE_NORMAL
  @Volatile private var running = false
  @Volatile private var muted = false
  @Volatile private var generation = 0

  var onMic: ((ByteArray) -> Unit)? = null
  var onLevel: ((String, Float) -> Unit)? = null

  private val callAttributes = AudioAttributes.Builder()
    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
    .build()

  @SuppressLint("MissingPermission")
  fun start() {
    previousMode = audioManager.mode
    audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
    useLoudspeaker()
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
      val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
        .setAudioAttributes(callAttributes)
        .build()
      audioManager.requestAudioFocus(request)
      focus = request
    }

    val micBytes = max(AudioRecord.getMinBufferSize(MIC_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT), MIC_CHUNK * 4)
    val mic = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, MIC_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, micBytes)
    if (mic.state != AudioRecord.STATE_INITIALIZED) {
      mic.release()
      restoreAudio()
      throw IllegalStateException("The microphone couldn't be opened.")
    }
    if (AcousticEchoCanceler.isAvailable()) echoCanceler = AcousticEchoCanceler.create(mic.audioSessionId)?.apply { enabled = true }
    if (NoiseSuppressor.isAvailable()) noiseSuppressor = NoiseSuppressor.create(mic.audioSessionId)?.apply { enabled = true }

    val playBytes = max(AudioTrack.getMinBufferSize(SPEECH_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT), SPEECH_RATE / 5)
    val player = AudioTrack.Builder()
      .setAudioAttributes(callAttributes)
      .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(SPEECH_RATE).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
      .setBufferSizeInBytes(playBytes)
      .setTransferMode(AudioTrack.MODE_STREAM)
      .build()

    record = mic
    track = player
    running = true
    mic.startRecording()
    player.play()

    micThread = Thread {
      val buffer = ByteArray(MIC_CHUNK)
      var lastLevel = 0L
      while (running) {
        val read = try {
          mic.read(buffer, 0, buffer.size)
        } catch (e: Exception) {
          -1
        }
        if (read <= 0) continue
        if (muted) continue
        val chunk = buffer.copyOf(read)
        onMic?.invoke(chunk)
        val now = System.currentTimeMillis()
        if (now - lastLevel >= 50) {
          lastLevel = now
          onLevel?.invoke("you", level(chunk))
        }
      }
    }.apply { name = "LiveAudioMic"; start() }

    playThread = Thread {
      while (running) {
        val chunk = try {
          speech.take()
        } catch (e: InterruptedException) {
          break
        }
        if (!running || chunk.isEmpty()) continue
        val written = generation
        onLevel?.invoke("tutor", level(chunk))
        var offset = 0
        // Small writes, so clear() takes effect within a few milliseconds.
        while (running && offset < chunk.size && written == generation) {
          val size = min(WRITE_BYTES, chunk.size - offset)
          val wrote = player.write(chunk, offset, size)
          if (wrote <= 0) break
          offset += wrote
        }
      }
    }.apply { name = "LiveAudioSpeech"; start() }
  }

  fun play(data: ByteArray) {
    if (running && data.isNotEmpty()) speech.offer(data)
  }

  /** Drops speech that hasn't been played yet (the learner talked over the tutor). */
  fun clear() {
    if (!running) return
    generation += 1
    speech.clear()
    track?.let {
      try {
        it.pause()
        it.flush()
        it.play()
      } catch (e: IllegalStateException) {
        // stopping
      }
    }
    onLevel?.invoke("tutor", 0f)
  }

  fun setMuted(value: Boolean) {
    muted = value
    if (value) onLevel?.invoke("you", 0f)
  }

  fun stop() {
    if (!running) return
    running = false
    speech.clear()
    speech.offer(ByteArray(0)) // wakes the speech thread
    micThread?.join(500)
    playThread?.join(500)
    micThread = null
    playThread = null
    try {
      record?.stop()
    } catch (e: IllegalStateException) {
      // never started
    }
    record?.release()
    record = null
    echoCanceler?.release()
    noiseSuppressor?.release()
    echoCanceler = null
    noiseSuppressor = null
    try {
      track?.stop()
    } catch (e: IllegalStateException) {
      // never started
    }
    track?.release()
    track = null
    restoreAudio()
  }

  private fun useLoudspeaker() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
      // Headphones or a headset when connected, otherwise the loudspeaker (not the earpiece).
      val devices = audioManager.availableCommunicationDevices
      val external = devices.firstOrNull {
        it.type == android.media.AudioDeviceInfo.TYPE_WIRED_HEADSET ||
          it.type == android.media.AudioDeviceInfo.TYPE_WIRED_HEADPHONES ||
          it.type == android.media.AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
          it.type == android.media.AudioDeviceInfo.TYPE_BLE_HEADSET ||
          it.type == android.media.AudioDeviceInfo.TYPE_USB_HEADSET
      }
      val speaker = devices.firstOrNull { it.type == android.media.AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
      (external ?: speaker)?.let { audioManager.setCommunicationDevice(it) }
    } else {
      @Suppress("DEPRECATION")
      audioManager.isSpeakerphoneOn = !audioManager.isWiredHeadsetOn
    }
  }

  private fun restoreAudio() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
      audioManager.clearCommunicationDevice()
    } else {
      @Suppress("DEPRECATION")
      audioManager.isSpeakerphoneOn = false
    }
    audioManager.mode = previousMode
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) focus?.let { audioManager.abandonAudioFocusRequest(it) }
    focus = null
  }

  private fun level(chunk: ByteArray): Float {
    val samples = chunk.size / 2
    if (samples == 0) return 0f
    var sum = 0.0
    for (i in 0 until samples) {
      val value = ((chunk[i * 2].toInt() and 0xff) or (chunk[i * 2 + 1].toInt() shl 8)).toShort() / 32768.0
      sum += value * value
    }
    val db = 20 * log10(max(sqrt(sum / samples), 1e-5))
    val normal = min(1.0, max(0.0, (db + 60) / 60))
    return (normal * normal).toFloat()
  }

  companion object {
    const val MIC_RATE = 16000
    const val SPEECH_RATE = 24000
    const val MIC_CHUNK = 1280 // 40 ms of 16 kHz audio
    const val WRITE_BYTES = 1920 // 40 ms of 24 kHz audio
  }
}
