import ExpoModulesCore

// Live Talk-back audio: an echo-cancelled microphone (16 kHz PCM out) and a
// speech player (24 kHz PCM in, what Gemini Live sends), both as base64.
// Events: onMic { data: base64 }, onLevel { who: "you" | "tutor", level: 0...1 }.
public class LiveAudioModule: Module {
  private var engine: LiveAudioEngine?

  public func definition() -> ModuleDefinition {
    Name("LiveAudio")

    Events("onMic", "onLevel")

    AsyncFunction("start") { () -> Bool in
      if self.engine != nil {
        return true
      }
      let engine = try LiveAudioEngine()
      engine.onMic = { [weak self] data in
        self?.sendEvent("onMic", ["data": data.base64EncodedString()])
      }
      engine.onLevel = { [weak self] who, level in
        self?.sendEvent("onLevel", ["who": who, "level": level])
      }
      try engine.start()
      self.engine = engine
      return true
    }

    Function("setMuted") { (muted: Bool) in
      self.engine?.setMuted(muted)
    }

    Function("play") { (base64: String) in
      guard let data = Data(base64Encoded: base64) else {
        return
      }
      self.engine?.play(data)
    }

    Function("clear") {
      self.engine?.clear()
    }

    Function("stop") {
      self.engine?.stop()
      self.engine = nil
    }

    OnDestroy {
      self.engine?.stop()
      self.engine = nil
    }
  }
}
