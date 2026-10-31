package app.memorypal.liveaudio

import android.util.Base64
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

// Live Talk-back audio: an echo-cancelled microphone (16 kHz PCM out) and a
// speech player (24 kHz PCM in, what Gemini Live sends), both as base64.
// Events: onMic { data: base64 }, onLevel { who: "you" | "tutor", level: 0..1 }.
class LiveAudioModule : Module() {
  private var engine: LiveAudioEngine? = null

  override fun definition() = ModuleDefinition {
    Name("LiveAudio")

    Events("onMic", "onLevel")

    AsyncFunction("start") {
      if (engine != null) return@AsyncFunction true
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      val made = LiveAudioEngine(context)
      made.onMic = { data -> sendEvent("onMic", mapOf("data" to Base64.encodeToString(data, Base64.NO_WRAP))) }
      made.onLevel = { who, level -> sendEvent("onLevel", mapOf("who" to who, "level" to level)) }
      made.start()
      engine = made
      true
    }

    Function("setMuted") { muted: Boolean ->
      engine?.setMuted(muted)
    }

    Function("play") { base64: String ->
      val data = try {
        Base64.decode(base64, Base64.DEFAULT)
      } catch (e: IllegalArgumentException) {
        null
      }
      if (data != null) engine?.play(data)
    }

    Function("clear") {
      engine?.clear()
    }

    Function("stop") {
      engine?.stop()
      engine = null
    }

    OnDestroy {
      engine?.stop()
      engine = null
    }
  }
}
